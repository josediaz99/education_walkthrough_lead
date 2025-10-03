from website import create_app,bootstrap_db


app = create_app()

if __name__ == "__main__":
    bootstrap_db(app)
    app.run(debug=True)