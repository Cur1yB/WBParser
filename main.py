import json
from datetime import date
from os import path
import pandas as pd
import requests

class ProductDataExtractor:

    def __init__(self):
        # Инициализация класса с базовыми параметрами
        self.headers = {'Accept': "*/*", 'User-Agent': "Chrome/51.0.2704.103 Safari/537.36"}
        self.run_date = date.today()
        self.products_info = []  # Список для хранения информации о товарах
        self.directory = path.dirname(__file__)

    def fetch_catalog(self) -> str:
        # Загрузка каталога товаров с сервера Wildberries
        local_catalog_path = path.join(self.directory, 'catalog.json')
        if (not path.exists(local_catalog_path)
                or date.fromtimestamp(int(path.getmtime(local_catalog_path)))
                > self.run_date):
            url = ('https://static-basket-01.wb.ru/vol0/data/'
                   'main-menu-ru-ru-v2.json')
            response = requests.get(url, headers=self.headers).json()
            # Сохранение каталога в локальный JSON-файл
            with open(local_catalog_path, 'w', encoding='UTF-8') as my_file:
                json.dump(response, my_file, indent=2, ensure_ascii=False)
        return local_catalog_path

    def traverse_categories(self, parent_categories: list, flattened_catalog: list):
        # Рекурсивный обход категорий для построения плоского списка
        for category in parent_categories:
            try:
                # Добавление информации о категории в плоский список
                flattened_catalog.append({
                    'name': category['name'],
                    'url': category['url'],
                    'shard': category['shard'],
                    'query': category['query']
                })
            except KeyError:
                continue
            if 'childs' in category:
                # Рекурсивный вызов для дочерних категорий
                self.traverse_categories(category['childs'], flattened_catalog)

    def process_catalog(self, local_catalog_path: str) -> list:
        # Обработка загруженного каталога и построение плоского списка
        catalog = []
        with open(local_catalog_path, 'r', encoding='utf-8') as my_file:
            self.traverse_categories(json.load(my_file), catalog)
        return catalog

    def extract_category_data(self, catalog: list, user_input: str) -> tuple:
        # Извлечение информации о категории из плоского списка
        for category in catalog:
            if (user_input.split("https://www.wildberries.ru")[-1]
                    == category['url'] or user_input == category['name']):
                return category['name'], category['shard'], category['query']

    def fetch_products_on_page(self, page_data: dict) -> list:
        # Извлечение информации о товарах на странице
        products_on_page = []
        for item in page_data['data']['products']:
            products_on_page.append({
                'Link': f"https://www.wildberries.ru/catalog/"
                        f"{item['id']}/detail.aspx",
                'Article': item['id'],
                'Name': item['name'],
                'Brand': item['brand'],
                'Brand ID': item['brandId'],
                'Price': int(item['priceU'] / 100),
                'Sale Price': int(item['salePriceU'] / 100),
                'Rating': item['rating'],
                'Feedbacks': item['feedbacks']
            })
        return products_on_page

    def add_data_from_page(self, url: str):
        # Загрузка и добавление информации о товарах со страницы
        response = requests.get(url, headers=self.headers).json()
        page_data = self.fetch_products_on_page(response)
        if len(page_data) > 0:
            self.products_info.extend(page_data)
            print(f"Added products: {len(page_data)}")
        else:
            print('Loading of products completed')
            return True

    def fetch_products_in_category(self, category_data: tuple):
        # Загрузка товаров из определенной категории
        for page in range(1, 101):
            print(f"Fetching products from page {page}")
            url = (f"https://catalog.wb.ru/catalog/{category_data[1]}/"
                   f"catalog?appType=1&curr=rub"
                   f"&dest=-1075831,-77677,-398551,12358499&page={page}"
                   f"&reg=0&sort=popular&spp=0&{category_data[2]}")
            if self.add_data_from_page(url):
                break

    def fetch_sales_data(self):
        # Загрузка информации о продажах для каждого товара
        for product in self.products_info:
            url = (f"https://product-order-qnt.wildberries.ru/by-nm/"
                   f"?nm={product['Article']}")
            try:
                response = requests.get(url, headers=self.headers).json()
                product['Sold'] = response[0]['qnt']
            except requests.ConnectTimeout:
                product['Sold'] = 'no data'
            print(f"Collected cards: {self.products_info.index(product) + 1}"
                  f" out of {len(self.products_info)}")

    def save_to_excel(self, file_name: str) -> str:
        # Сохранение информации о товарах в Excel-файл
        data = pd.DataFrame(self.products_info)
        result_path = (f"{path.join(self.directory, file_name)}_"
                       f"{self.run_date.strftime('%Y-%m-%d')}.xlsx")
        writer = pd.ExcelWriter(result_path)
        data.to_excel(writer, 'data', index=False)
        writer.close()
        return result_path

    def fetch_products_in_search_results(self, key_word: str):
        # Загрузка товаров по ключевому слову
        for page in range(1, 101):
            print(f"Fetching products from page {page}")
            url = (f"https://search.wb.ru/exactmatch/ru/common/v4/search?"
                   f"appType=1&curr=rub"
                   f"&dest=-1029256,-102269,-2162196,-1257786"
                   f"&page={page}&pricemarginCoeff=1.0"
                   f"&query={'%20'.join(key_word.split())}]&reg=0"
                   f"&resultset=catalog&sort=popular&spp=0")
            if self.add_data_from_page(url):
                break

    def run_parser(self):
        # Основная функция для запуска парсера
        instructions = """Enter 1 for parsing the whole category,
        2 - for keyword-based parsing: """
        mode = input(instructions)
        if mode == '1':
            local_catalog_path = self.fetch_catalog()
            print(f"Catalog saved: {local_catalog_path}")
            processed_catalog = self.process_catalog(local_catalog_path)
            input_category = input("Enter the category name or URL: ")
            category_data = self.extract_category_data(processed_catalog,
                                                       input_category)
            if category_data is None:
                print("Category not found")
            else:
                print(f"Found category: {category_data[0]}")
            self.fetch_products_in_category(category_data)
            self.fetch_sales_data()
            print(f"Data saved to {self.save_to_excel(category_data[0])}")
        if mode == '2':
            key_word = input("Enter search query: ")
            self.fetch_products_in_search_results(key_word)
            self.fetch_sales_data()
            print(f"Data saved to {self.save_to_excel(key_word)}")

if __name__ == '__main__':
    app = ProductDataExtractor()
    app.run_parser()
