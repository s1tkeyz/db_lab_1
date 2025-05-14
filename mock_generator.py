import csv
from faker import Faker
from datetime import datetime, timedelta
import random

# Инициализация Faker
fake = Faker()

# Функция для генерации случайной даты в заданном диапазоне
def generate_random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)

# Функция для генерации данных
def generate_ticket_data(batch_size):
    data = []
    for _ in range(batch_size):
        ticket_uuid = fake.uuid4()
        passenger_name = fake.name()
        passenger_email = f"{fake.user_name()}@{fake.domain_name()}"
        flight_number = fake.lexify('??').upper() + str(fake.random_int(min=100, max=9999))
        departure_city = fake.city()
        arrival_city = fake.city()
        departure_date = generate_random_date(datetime(2022, 1, 1), datetime(2025, 1, 1)).strftime('%Y-%m-%d')
        ticket_price = round(random.uniform(50, 1000), 2)
        has_luggage = random.choice([True, False])
        birth_date = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime('%Y-%m-%d')
        passport_number = fake.bothify(text='??-###-###-###-??#').upper()

        # Добавление строки в данные
        data.append([
            ticket_uuid,
            passenger_name,
            passenger_email,
            flight_number,
            departure_city,
            arrival_city,
            departure_date,
            ticket_price,
            has_luggage,
            birth_date,
            passport_number
        ])
    return data

# Функция для записи данных в CSV файл
def write_to_csv(data, filename):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Заголовки колонок
        writer.writerow([
            "ticket_uuid",
            "passenger_name",
            "passenger_email",
            "flight_number",
            "departure_city",
            "arrival_city",
            "departure_date",
            "ticket_price",
            "has_luggage",
            "birth_date",
            "passport_number"
        ])
        # Запись данных
        writer.writerows(data)

# Основная функция
def main():
    total_rows = 5000000
    batch_size = 5000000
    data_dir = "./mock_data"
    
    batches = total_rows // batch_size
    
    for i in range(batches):
        print(f"Generating batch #{i + 1}...")
        data = generate_ticket_data(batch_size)
        write_to_csv(data, f"{data_dir}/mock_batch_{i + 1}.csv")
    
    print("Finished.")

if __name__ == "__main__":
    main()
