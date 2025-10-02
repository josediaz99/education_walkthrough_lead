# education_walkthrough_lead

# Setup & installation

clone repository

    git clone https://github.com/josediaz99/education_walkthrough_lead.git

installs required to run the program

    pip install -r requirements.txt

in init file change secret key inside of createApp() function

dir_ed_entities.xls illinois school district data only used for testing in searchThroughQuery instead of making calls to school digger api

- testing can be resplaced with calls to database once filled (not using random data from school digger developer access)

# Running the app

create a .env file (you can use this command when youre inside directory)

    touch .env

inside .env file store app id and api key (store api key and app id exacly as written typed here)

    SCHOOLDIGGER_APP_ID = example123
    SCHOOLDIGGER_APP_KEY = example123412342134

run main.py
