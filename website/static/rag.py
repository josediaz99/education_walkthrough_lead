from unstructured.partition.auto import partition
import io
import boto3
from botocore.client import Config
from dotenv import load_dotenv, dotenv_values
from pydantic import BaseModel, Field
import base64
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.rate_limiters import InMemoryRateLimiter
import hashlib
import itertools
import uuid
from langchain_classic.retrievers import MultiVectorRetriever
from langchain_classic.storage import InMemoryStore
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import SystemMessage, HumanMessage
# from langchain.load import dumps, loads

load_dotenv()
SCHOOL_DISTRICT_BUCKET_FOLDER = os.getenv("SCHOOL_DISTRICT_BUCKET_FOLDER")  # replace with your actual API key
DOC_BUCKET_FOLDER = os.getenv("DOC_BUCKET_FOLDER")

s3_client = boto3.client("s3", region_name="us-east-2", config=Config(signature_version="s3v4"))

vectorstore = Chroma(collection_name="summaries", embedding_function=OpenAIEmbeddings())

store = InMemoryStore()
id_key = "doc_id"

retriever = MultiVectorRetriever(
    vectorstore=vectorstore,
    docstore=store,
    id_key=id_key,
    search_kwargs={"k": 5}
)

# MULTI-QUERY GENERATION

multi_query_prompt_template = """You are an AI language model assistant. Your task is to generate five 
different versions of the given user question to retrieve relevant documents from a vector 
database. By generating multiple perspectives on the user question, your goal is to help
the user overcome some of the limitations of the distance-based similarity search. 
Provide these alternative questions separated by newlines. Original question: {question}"""

multi_query_prompt = ChatPromptTemplate.from_template(multi_query_prompt_template)

generate_queries = (
    multi_query_prompt 
    | ChatOpenAI(temperature=0) 
    | StrOutputParser() 
    | (lambda x: x.split("\n"))
)

rate_limiter = InMemoryRateLimiter(requests_per_second=2, check_every_n_seconds=0.1, max_bucket_size=10)

# IMAGE SUMMARIZATION

img_summarization_model = ChatOpenAI(model="gpt-4o", rate_limiter=rate_limiter)

img_table_summarization_prompt_text = """Describe the image in detail. For context,
                the image is part of a school district's improvement plan document.
                Be specific about graphs and text content.
                Respond only with the description of the image, no additional comment.
                """

img_table_summarization_messages = [
    (
        "user",
        [
            {
                "type": "text",
                "text": img_table_summarization_prompt_text
            },
            {
                "type": "image_url",
                "image_url": {"url": "{image}"}
            }
        ]
    )
]

img_table_summarization_prompt = ChatPromptTemplate.from_messages(img_table_summarization_messages)

img_table_summarize_chain = img_table_summarization_prompt | img_summarization_model | StrOutputParser()

class SummaryItem(BaseModel):
    id: str = Field(description="Stable ID you provide for each input element.")
    summary: str = Field(description="Extractive, concise summary for the element with this id.")

class BatchSummaryResponse(BaseModel):
    items: list[SummaryItem] = Field(description="One summary per input id, preserving all ids.")

class ResponseSchema(BaseModel):
    answer: str = Field(description="The answer to the user's question based on the provided context.")
    is_affirmative: bool = Field(description="Indicates whether the answer is affirmative or not.")
    sources: list[str] = Field(description="A list of sources used to generate the answer.")

def upload_image(image_base64):
    img_data = base64.b64decode(image_base64)
    s3_client.upload_fileobj(
        io.BytesIO(img_data),
        "education-walkthrough",
        f"{SCHOOL_DISTRICT_BUCKET_FOLDER}/{DOC_BUCKET_FOLDER}/image_{i}.jpg",
        ExtraArgs={"ContentType": "image/jpg"}
    )

    return f"{SCHOOL_DISTRICT_BUCKET_FOLDER}/{DOC_BUCKET_FOLDER}/image_{i}.jpg"

def get_presigned_urls(image_keys):
    urls = []
    for key in image_keys:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': 'education-walkthrough', 'Key': key},
            ExpiresIn=300)
        urls.append(url)
    return urls

def extract(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    elements = partition(
        url=url, 
        headers=headers,
        strategy="hi_res",
        extract_image_block_types=["Image", "Table"],
        extract_image_block_to_payload=True,
        max_characters=10000,
        combine_text_under_n_chars=2000,
        new_after_n_chars=6000
    )

    images = [el.metadata.image_base64 for el in elements if 'Image' in str(type(el)) or 'Table' in str(type(el))]
    image_keys = []
    
    for i in range(len(images)):
        image_keys.append(upload_image(images[i]))

    image_urls = get_presigned_urls(image_keys)

    texts = [el for el in elements if 'Text' in str(type(el))]

    return texts, images, image_urls

def make_text_items(docs):
    items = []
    for doc in docs:
        # Create a stable ID by hashing the text content
        id_hash = hashlib.sha256(doc.text.encode('utf-8')).hexdigest()
        items.append({"id": id_hash, "text": doc.text})
    return items

def make_img_items(docs):
    items = []
    for i, doc in enumerate(docs):
        # Create a stable ID by hashing the base64 content
        id_hash = hashlib.sha256(doc.encode('utf-8')).hexdigest()
        items.append((
            "user",
            [
                {"type": "text", "text": f"ITEM_START id={id_hash}"},
                {"type": "image_url", "image_url": {"url": doc}},
                {"type": "text", "text": f"ITEM_END id={id_hash}"},
            ],
        ))
    return items

def chunked(iterable, n):
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, n))
        if not chunk:
            break
        yield {"items": chunk}

def get_unique_docs(docs_lst):
    unique_docs = []

    for docs in docs_lst:
        for doc in docs:
            if(doc not in unique_docs):
                unique_docs.append(doc)

    return unique_docs

def parse_docs(docs):
    retrieved_images, retrieved_texts = [], []

    for doc in docs:
        try:
            base64.b64decode(doc)
            retrieved_images.append(doc)
        except Exception as e:
            retrieved_texts.append(doc)

    return {
        "images": retrieved_images,
        "texts": retrieved_texts
    }

def build_prompt(kwargs):
    docs_by_type = kwargs["context"]
    user_question = kwargs["question"]

    context_text = ""
    for retrieved_text in docs_by_type["texts"]:
        context_text += retrieved_text.text

    prompt_text = f"""
        Answer the question based only on the following context, which can include text, tables, and the below image.
        Context: {context_text}
        Question: {user_question}
    """

    prompt_content = [{
        "type": "text",
        "text": prompt_text
    }]

    if(len(docs_by_type["images"]) > 0):
        for image in docs_by_type["images"]:
            prompt_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"}
                }
            )

    return ChatPromptTemplate(
        [
            HumanMessage(content=prompt_content)
        ]
    )

def generate_image_summaries(image_urls):
    
    img_batch_items = make_img_items(image_urls)

    img_batches = list(chunked(img_batch_items, 10))

    img_batch_responses = img_table_summarize_chain.batch(img_batches)

    image_summaries = []

    for batch_resp in img_batch_responses:
        image_summaries.extend([item.summary for item in batch_resp.items])
    
    return image_summaries

def store_elements(texts, images, image_summaries):
    if(len(texts) > 0):
        print("Storing text elements")
        text_ids = [str(uuid.uuid4()) for _ in texts]
        summary_texts = [Document(page_content=text.text, metadata={id_key: text_ids[i]}) for i, text in enumerate(texts)]
        retriever.vectorstore.add_documents(summary_texts)
        retriever.docstore.mset(list(zip(text_ids, texts)))

    if(len(images) > 0):
        print("Storing image elements")
        image_ids = [str(uuid.uuid4()) for _ in images]
        summary_images = [Document(page_content=img, metadata={id_key: image_ids[i]}) for i, img in enumerate(image_summaries)]
        retriever.vectorstore.add_documents(summary_images)
        retriever.docstore.mset(list(zip(image_ids, images)))
    
structured_chain_with_sources = {
    "context": generate_queries | retriever.map() | RunnableLambda(get_unique_docs) | RunnableLambda(parse_docs),
    "question": RunnablePassthrough()
} | RunnablePassthrough().assign(
    response = (
        RunnableLambda(build_prompt)
        | ChatOpenAI(model="gpt-4o").with_structured_output(ResponseSchema)
    )
)

def analyze_doc(url):
    print(f"Analyzing {url}")
    # Extract document
    texts, images, image_urls = extract(url)

    print(f"Texts: {texts}")
    print(f"Image URLs: {image_urls}")

    # Summarize images/tables
    image_summaries = generate_image_summaries(image_urls)

    # Store elements
    vectorstore = Chroma(collection_name="summaries", embedding_function=OpenAIEmbeddings())
    store_elements(texts, images, image_summaries)

    # Use RAG to figure out whether tags are present
    responses = {}

    frequency_response = structured_chain_with_sources.invoke("Are there mentions of low classroom observation/walkthrough frequency or increasing classroom observation/walkthrough frequency")
    print(f"Low Frequency:")
    print(frequency_response['response'].answer)
    for text in frequency_response['context']['texts']:
        print(text)
    if(frequency_response['response'].is_affirmative):
        responses['low_frequency'] = {
            "tag": "Low Frequency",
            "explanation": frequency_response['response'].answer
        }
    
    feedback_response = structured_chain_with_sources.invoke("Are there mentions of slow feedback from classroom observations/walkthroughs or a need to increase walkthrough/observation feedback response time?")
    print(f"Slow Feedback: {feedback_response['response'].answer}")
    if(feedback_response['response'].is_affirmative):
        responses['slow_feedback'] = {
            "tag": "Slow Feedback",
            "explanation": feedback_response['response'].answer
        }

    data_response = structured_chain_with_sources.invoke("Are there mentions of implementing data-driven improvement or evaluations?")
    print(f"Data Driven Improvement: {data_response['response'].answer}")
    if(data_response['response'].is_affirmative):
        responses['data_driven'] = {
            "tag": "Data Driven Improvement",
            "explanation": data_response['response'].answer
        }

    pd_response = structured_chain_with_sources.invoke("Are there mentions of professional development?")
    if(pd_response['response'].is_affirmative):
        responses['professional_development'] = {
            "tag": "Professional Development",
            "explanation": pd_response['response'].answer
        }

    avid_response = structured_chain_with_sources.invoke("Are there mentions of being Advancement Via Individual Determination (AVID) certified or seeking AVID certification?")
    if(avid_response['response'].is_affirmative):
        responses['avid'] = {
            "tag": "AVID",
            "explanation": avid_response['response'].answer
        }

    ap_response = structured_chain_with_sources.invoke("Are there mentions of being Advanced Placement (AP) certified or seeking AP certification?")
    if(ap_response['response'].is_affirmative):
        responses['ap'] = {
            "tag": "AP",
            "explanation": ap_response['response'].answer
        }

    ib_response = structured_chain_with_sources.invoke("Are there mentions of being International Baccalaureate (IB) certified or seeking IB certification?")
    if(ib_response['response'].is_affirmative):
        responses['ib'] = {
            "tag": "IB",
            "explanation": ib_response['response'].answer
        }

    grant_response = structured_chain_with_sources.invoke("Are there mentions of being awarded an instruction-related grant or seeking instruction-related grants?")
    if(grant_response['response'].is_affirmative):
        responses['instruction_related_grant'] = {
            "tag": "Instruction Related Grant",
            "explanation": grant_response['response'].answer
        }

    print(responses)

    return responses
