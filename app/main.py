from dotenv import load_dotenv
from app.engine import Engine


def main():
    load_dotenv()
    Engine().run("app/config/config.example.json")  # или app/config/config.json


if __name__ == "__main__":
    main()
