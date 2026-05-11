from app import create_app

# The application factory function creates and configures the app.
app = create_app()

if __name__ == '__main__':
    # This block only runs when you execute "python run.py"
    app.run(debug=True)





