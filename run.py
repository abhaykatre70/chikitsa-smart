from app.app import app, create_tables, seed_data
import os

if __name__ == "__main__":
    create_tables()
    seed_data()
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
