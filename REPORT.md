## **Лабораторная работа 1 / Индексы, транзакции, расширения PostgreSQL**

**Выполнил:** ст-т Даутов Т. Б.

**Группа:** 306


### 1.1 Индексы

Предметная область - авиабилеты.
Создадим таблицу:

```sql
create table if not exists tickets (
  ticket_uuid TEXT,
  passenger_name TEXT,
  passenger_email TEXT,
  flight_number TEXT,
  departure_city TEXT,
  arrival_city TEXT,
  departure_date DATE,
  ticket_price MONEY,
  has_luggage BOOLEAN,
  birth_date DATE,
  passport_number TEXT
)
```

Для генерации тестовых данных использовался скрипт `mock_generator.csv`.

**Без индекса**

Запрос на точный поиск значения (находим все билеты с отправлением в определенную дату):

```sql
explain analyze
select * from tickets where departure_date = '2023-05-17'
```

```
Gather  (cost=1000.00..141283.47 rows=4528 width=149) (actual time=3.493..1353.324 rows=4768 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Seq Scan on tickets  (cost=0.00..139830.67 rows=1887 width=149) (actual time=3.385..1316.028 rows=1589 loops=3)
        Filter: (departure_date = '2023-05-17'::date)
        Rows Removed by Filter: 1665077
Planning Time: 0.088 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 0.923 ms (Deform 0.502 ms), Inlining 0.000 ms, Optimization 0.704 ms, Emission 8.831 ms, Total 10.459 ms
Execution Time: 1354.008 ms
```

Выше видно, что при выполнении запроса использовался "тупой" просмотр всех строк двумя параллельными воркерами. 

Запрос на поиск значений в диапазоне (ищем строки, в которых дата вылета попадает в заданный диапазон):
```sql
explain analyze
select * from tickets where departure_date between '2024-01-01' and '2024-01-31' ; 
```

```
Gather  (cost=1000.00..159542.80 rows=135038 width=149) (actual time=3.006..1325.178 rows=140908 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Seq Scan on tickets  (cost=0.00..145039.00 rows=56266 width=149) (actual time=4.386..890.049 rows=46969 loops=3)
        Filter: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
        Rows Removed by Filter: 1619697
Planning Time: 0.103 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.385 ms (Deform 0.665 ms), Inlining 0.000 ms, Optimization 0.860 ms, Emission 12.170 ms, Total 14.415 ms
Execution Time: 1411.483 ms
```

Тут ситуация аналогичная.

Запрос на текстовый поиск по шаблону (ищем пассажиров с именем Mike и фамилией, начинающейся на De):

```sql
explain analyze
select * from tickets where passenger_name like 'Mike De%';
```

```
Gather  (cost=1000.00..140879.87 rows=492 width=149) (actual time=11.836..1149.294 rows=9 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Seq Scan on tickets  (cost=0.00..139830.67 rows=205 width=149) (actual time=346.953..1093.574 rows=3 loops=3)
        Filter: (passenger_name ~~ 'Mike De%'::text)
        Rows Removed by Filter: 1666664
Planning Time: 0.122 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 0.728 ms (Deform 0.278 ms), Inlining 0.000 ms, Optimization 0.616 ms, Emission 8.250 ms, Total 9.594 ms
Execution Time: 1149.616 ms
```

Еще сделаем запрос посложнее (со сложным условием и группировкой):
```sql
explain analyze
select avg(ticket_price) from tickets where (flight_number like 'SU%') and (departure_date between '2022-09-01' and '2022-09-30')
group by has_luggage;
```

```
Finalize GroupAggregate  (cost=151247.43..151248.02 rows=2 width=33) (actual time=1948.408..2022.114 rows=2 loops=1)
  Group Key: has_luggage
  ->  Gather Merge  (cost=151247.43..151247.97 rows=4 width=33) (actual time=1948.388..2022.098 rows=6 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Partial GroupAggregate  (cost=150247.41..150247.48 rows=2 width=33) (actual time=1929.110..1929.117 rows=2 loops=3)
              Group Key: has_luggage
              ->  Sort  (cost=150247.41..150247.43 rows=6 width=7) (actual time=1929.064..1929.067 rows=65 loops=3)
                    Sort Key: has_luggage
                    Sort Method: quicksort  Memory: 26kB
                    Worker 0:  Sort Method: quicksort  Memory: 26kB
                    Worker 1:  Sort Method: quicksort  Memory: 26kB
                    ->  Parallel Seq Scan on tickets  (cost=0.00..150247.33 rows=6 width=7) (actual time=114.782..1928.926 rows=65 loops=3)
                          Filter: (((flight_number)::text ~~ 'SU%'::text) AND (departure_date >= '2022-09-01'::date) AND (departure_date <= '2022-09-30'::date))
                          Rows Removed by Filter: 1666601
Planning Time: 0.159 ms
JIT:
  Functions: 30
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 3.219 ms (Deform 1.382 ms), Inlining 0.000 ms, Optimization 1.648 ms, Emission 28.850 ms, Total 33.717 ms
Execution Time: 2023.896 ms
```

**С b-tree индексом**

Теперь перейдем к индексам.
Это универсальный вид индекса, используемый по умолчанию в PostgreSQL. Он основан на
концепции одноименных сбалансированных деревьях.

Построим b-tree индекс над столбцом departure_date:

```sql
drop index if exists idx_btree_departure_date;
create index idx_btree_departure_date on tickets(departure_date);
```

Индекс строился 8.1 секунд. Размер - 34 МБ.
Теперь проверим, как изменится время выполнения запросов.

```sql
explain analyze
select * from tickets where departure_date = '2023-05-17';
```

```
Bitmap Heap Scan on tickets  (cost=51.52..15236.97 rows=4528 width=149) (actual time=2.481..136.873 rows=4768 loops=1)
  Recheck Cond: (departure_date = '2023-05-17'::date)
  Heap Blocks: exact=4678
  ->  Bitmap Index Scan on idx_btree_departure_date  (cost=0.00..50.39 rows=4528 width=0) (actual time=1.764..1.765 rows=4768 loops=1)
        Index Cond: (departure_date = '2023-05-17'::date)
Planning Time: 0.351 ms
Execution Time: 137.263 ms
```
Видим, что тут всё сработало существенно быстрее, благодаря индексу. Используется Bitmap сканирование по 
построенному нами индексу.

```sql
explain analyze
select * from tickets where departure_date between '2024-01-01' and '2024-01-31';
```

```
Gather  (cost=2848.57..155423.83 rows=135038 width=149) (actual time=85.757..2280.228 rows=140908 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Bitmap Heap Scan on tickets  (cost=1848.57..140920.03 rows=56266 width=149) (actual time=38.077..2031.675 rows=46969 loops=3)
        Recheck Cond: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
        Rows Removed by Index Recheck: 466766
        Heap Blocks: exact=17573 lossy=12003
        ->  Bitmap Index Scan on idx_btree_departure_date  (cost=0.00..1814.81 rows=135038 width=0) (actual time=73.533..73.533 rows=140908 loops=1)
              Index Cond: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
Planning Time: 0.234 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.559 ms (Deform 0.669 ms), Inlining 0.000 ms, Optimization 1.024 ms, Emission 12.263 ms, Total 14.847 ms
Execution Time: 2287.222 ms
```

А тут ощутимо медленнее...

Выяснолось, что был взят слишком большой промежуток - месяц. Далее я попробовал запустить на 2024-01-01 до 2024-01-07 - отработало за 800 мс и индекс сработал.


**С BRIN (Block Range Index) индексом**

Этот тип индекса предназначен для обработки очень больших таблиц, в которых значение индексируемого столбца имеет некоторую естественную корреляцию с физическим положением строки в таблице. Он строит и использует сводную информацию о группах страниц.

Индекс построился за 2.4 секунды, размер - 64 кБ. Быстро и компактно.

```sql
explain analyze
select * from tickets where departure_date = '2023-05-17';
```

```
Gather  (cost=1031.22..136475.12 rows=4528 width=149) (actual time=9.024..3565.719 rows=4768 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Bitmap Heap Scan on tickets  (cost=31.22..135022.32 rows=1887 width=149) (actual time=13.853..3524.294 rows=1589 loops=3)
        Recheck Cond: (departure_date = '2023-05-17'::date)
        Rows Removed by Index Recheck: 1665077
        Heap Blocks: lossy=40983
        ->  Bitmap Index Scan on idx_brin_departure_date  (cost=0.00..30.09 rows=1773301 width=0) (actual time=4.721..4.721 rows=1137890 loops=1)
              Index Cond: (departure_date = '2023-05-17'::date)
Planning Time: 0.263 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.235 ms (Deform 0.614 ms), Inlining 0.000 ms, Optimization 0.803 ms, Emission 9.583 ms, Total 11.622 ms
Execution Time: 3566.664 ms
```

```sql
explain analyze
select * from tickets where departure_date between '2024-01-01' and '2024-01-31'; 
```

```
Gather  (cost=1000.00..159542.80 rows=135038 width=149) (actual time=5.366..1945.539 rows=140908 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Seq Scan on tickets  (cost=0.00..145039.00 rows=56266 width=149) (actual time=4.029..1819.647 rows=46969 loops=3)
        Filter: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
        Rows Removed by Filter: 1619697
Planning Time: 0.110 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.284 ms (Deform 0.562 ms), Inlining 0.000 ms, Optimization 0.812 ms, Emission 11.124 ms, Total 13.219 ms
Execution Time: 1951.987 ms
```

Оба запроса сейчас отработали неэффективно и сильно медленнее, чем вообще без индексов.
Это связано с сутью BRIN индекса.
Давайте отсортируем нашу таблицу по столбцу departure_date (создадим корреляцию) и заново построим индекс и попробуем прогнать те же запросы в отсортированной.

```sql
explain analyze
select * from tickets_sorted where departure_date = '2023-05-17';
```

```
Bitmap Heap Scan on tickets_sorted  (cost=21.14..18412.99 rows=4452 width=149) (actual time=1.552..15.734 rows=4768 loops=1)
  Recheck Cond: (departure_date = '2023-05-17'::date)
  Rows Removed by Index Recheck: 6479
  Heap Blocks: lossy=256
  ->  Bitmap Index Scan on idx_brin_departure_date_sorted  (cost=0.00..20.03 rows=5618 width=0) (actual time=0.441..0.442 rows=2560 loops=1)
        Index Cond: (departure_date = '2023-05-17'::date)
Planning Time: 0.104 ms
Execution Time: 16.073 ms
```

```sql
explain analyze
select * from tickets_sorted where departure_date between '2024-01-01' and '2024-01-31';
```

```
Gather  (cost=1058.88..156636.60 rows=151930 width=149) (actual time=11.241..148.963 rows=140908 loops=1)
  Workers Planned: 2
  Workers Launched: 2
  ->  Parallel Bitmap Heap Scan on tickets_sorted  (cost=58.88..140443.60 rows=63304 width=149) (actual time=6.138..51.116 rows=46969 loops=3)
        Recheck Cond: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
        Rows Removed by Index Recheck: 1773
        Heap Blocks: lossy=824
        ->  Bitmap Index Scan on idx_brin_departure_date_sorted  (cost=0.00..20.90 rows=157309 width=0) (actual time=2.134..2.135 rows=33280 loops=1)
              Index Cond: ((departure_date >= '2024-01-01'::date) AND (departure_date <= '2024-01-31'::date))
Planning Time: 0.152 ms
JIT:
  Functions: 6
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 1.211 ms (Deform 0.661 ms), Inlining 0.000 ms, Optimization 0.944 ms, Emission 14.619 ms, Total 16.773 ms
Execution Time: 260.908 ms
```

```sql
explain analyze
select avg(ticket_price) from tickets_sorted where (flight_number like 'SU%') and (departure_date between '2022-09-01' and '2022-09-30')
group by has_luggage;
```

```
Finalize GroupAggregate  (cost=143370.40..143375.19 rows=2 width=33) (actual time=265.741..271.328 rows=2 loops=1)
  Group Key: has_luggage
  ->  Gather Merge  (cost=143370.40..143375.13 rows=4 width=33) (actual time=265.717..271.309 rows=6 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Partial GroupAggregate  (cost=142370.38..142374.65 rows=2 width=33) (actual time=216.484..216.491 rows=2 loops=3)
              Group Key: has_luggage
              ->  Sort  (cost=142370.38..142371.79 rows=566 width=7) (actual time=216.440..216.444 rows=65 loops=3)
                    Sort Key: has_luggage
                    Sort Method: quicksort  Memory: 26kB
                    Worker 0:  Sort Method: quicksort  Memory: 26kB
                    Worker 1:  Sort Method: quicksort  Memory: 26kB
                    ->  Parallel Bitmap Heap Scan on tickets_sorted  (cost=21.11..142344.50 rows=566 width=7) (actual time=53.081..216.374 rows=65 loops=3)
                          Recheck Cond: ((departure_date >= '2022-09-01'::date) AND (departure_date <= '2022-09-30'::date))
                          Rows Removed by Index Recheck: 1192
                          Filter: ((flight_number)::text ~~ 'SU%'::text)
                          Rows Removed by Filter: 45605
                          Heap Blocks: lossy=1280
                          ->  Bitmap Index Scan on idx_brin_departure_date_sorted  (cost=0.00..20.77 rows=134836 width=0) (actual time=1.673..1.674 rows=32000 loops=1)
                                Index Cond: ((departure_date >= '2022-09-01'::date) AND (departure_date <= '2022-09-30'::date))
Planning Time: 0.237 ms
JIT:
  Functions: 36
  Options: Inlining false, Optimization false, Expressions true, Deforming true
  Timing: Generation 3.372 ms (Deform 1.787 ms), Inlining 0.000 ms, Optimization 2.092 ms, Emission 145.602 ms, Total 151.066 ms
Execution Time: 273.168 ms
```
Преимущество очевидно. Запросы отработали очень быстро.

Этот тип индекса довольно компактен и крайне полезен для поиска по отсортированным данным.


**С GIN (Generalized Inverted Index) индексом**

Это сложный тип индекса, предназначенный для случаев, когда индексируемые значения являются составными, а запросы, на обработку которых рассчитан индекс, ищут значения элементов в этих составных объектах. Например, такими объектами могут быть документы (строки), а запросы могут выполнять поиск документов, содержащих определённые слова (символы).

Тут нам понадобятся следующие расширения:

```sql
create extension if not exists pg_trgm; -- триграммы
create extension if not exists pg_bigm; -- биграммы
```

Построим GIN индекс с помощью pg_trgm над passenger_name.
Индекс строился 37 секунд, размер - 148 МБ (много).

```sql
explain analyze
select * from tickets where passenger_name like 'Mike De%';
```

```
Bitmap Heap Scan on tickets  (cost=298.52..2171.91 rows=492 width=149) (actual time=15.479..21.980 rows=9 loops=1)
  Recheck Cond: (passenger_name ~~ 'Mike De%'::text)
  Rows Removed by Index Recheck: 1
  Heap Blocks: exact=10
  ->  Bitmap Index Scan on idx_gin_passenger_name  (cost=0.00..298.40 rows=492 width=0) (actual time=15.453..15.454 rows=10 loops=1)
        Index Cond: (passenger_name ~~ 'Mike De%'::text)
Planning Time: 0.208 ms
Execution Time: 22.004 ms

```

Ещё докинем bigm на flight_number. В этом случае индекс строился 19 секунд и занял 72 МБ.

```sql
explain analyze
select avg(ticket_price) from tickets where (flight_number like 'SU%') and (departure_date between '2022-09-01' and '2022-09-30')
group by has_luggage;
```

```
GroupAggregate  (cost=1991.50..1991.63 rows=2 width=33) (actual time=417.012..417.031 rows=2 loops=1)
  Group Key: has_luggage
  ->  Sort  (cost=1991.50..1991.54 rows=14 width=7) (actual time=416.964..416.977 rows=196 loops=1)
        Sort Key: has_luggage
        Sort Method: quicksort  Memory: 29kB
        ->  Bitmap Heap Scan on tickets  (cost=85.62..1991.23 rows=14 width=7) (actual time=16.966..416.778 rows=196 loops=1)
              Recheck Cond: ((flight_number)::text ~~ 'SU%'::text)
              Filter: ((departure_date >= '2022-09-01'::date) AND (departure_date <= '2022-09-30'::date))
              Rows Removed by Filter: 7156
              Heap Blocks: exact=7136
              ->  Bitmap Index Scan on idx_gin_flight_number  (cost=0.00..85.62 rows=500 width=0) (actual time=7.537..7.538 rows=7352 loops=1)
                    Index Cond: ((flight_number)::text ~~ 'SU%'::text)
Planning Time: 0.407 ms
Execution Time: 417.080 ms
```


### 1.2 Транзакции

Транзакция — это набор операций по работе с базой данных (БД), объединенных в одну атомарную пачку. Основную суть
можно выразить так: "либо все, либо ничего". При возникновении ошибки при выполнении операции в транзакции она прекращается
и происходит откат (rollback) в исходное состояние.

Для дальнейшей работы создадим небольшие таблицы:

```sql
create table tickets_small as (
	select ticket_uuid, left(flight_number, 2) as aircompany, substr(flight_number, 3)::int as fnum, passenger_name, departure_date
	from tickets
	limit 100
);
```

```sql
create table passcount as (
	select aircompany, count(ticket_uuid) as passenger_count 
	from tickets_small
	group by aircompany
);
```

**Первая транзакция:** добавление информации о билете пассажира и увеличение счетчика пассажиров авиакомпании.

```sql
BEGIN;
INSERT INTO tickets_small (
    ticket_uuid,
    aircompany,
    fnum,
    passenger_name,
    departure_date
)
VALUES (
    'ldhcnlsdhalh',
    'MQ',
    3691,
    'Ivan Ivanov',
    '2025-05-07'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tickets_small WHERE name = 'Ivan Ivanov') THEN
        RAISE EXCEPTION 'Passenger Ivan Ivanov not found';
    END IF;

    UPDATE passcount
    SET passenger_count = passenger_count + 1
    WHERE aircompany = 'MQ';
COMMIT;
END $$;
ROLLBACK;
```

**Вторая транзакция:** отмена билета пассажира и уменьшение счетчика.

```sql
DO $$
DECLARE 
	var_aircompany TEXT;
BEGIN
	SELECT aircompany from tickets_small where passenger_name = 'Tony Jones';
	
	IF NOT FOUND THEN
    	RAISE EXCEPTION 'Passenger Tony Jones not found';
	END IF;
	
	DELETE FROM tickets_small WHERE passenger_name = 'Tony Jones';	

    UPDATE passcount
	SET passenger_count = passenger_count - 1
	WHERE aircompany = var_aircompany;
COMMIT;
END $$;
ROLLBACK;
```

**Уровни изоляции транзакций в SQL:**

1) READ UNCOMMITTED (Чтение незакоммиченного) - Самый низкий уровень изоляции. Допускает т.н. **"грязное чтение (dirty read)"**. В PostgreSQL не поддерживается и работает как READ COMMITTED.
2) READ COMMITTED (Чтение закоммиченного) - Каждая транзакция видит только закоммиченные данные. При этом транзакция видит и те подтвержденные изменения, которые внесли другие транзакции во время её исполнения. Это явление называется **неповторяющимся чтением (unrepeatable read)**. Это вид изоляции установлен в PostgreSQL по умолчанию.
3) REPEATABLE READ (Повторяемое чтение) - В этом режиме видны только те данные, которые были зафиксированы до начала транзакции, но не видны незафиксированные данные и изменения, произведённые другими транзакциями в процессе выполнения данной транзакции. Режим Repeatable Read строго гарантирует, что каждая транзакция видит полностью стабильное представление базы данных. Однако это представление не обязательно будет согласовано с некоторым последовательным выполнением транзакций одного уровня.
4) SERIALIZABLE (Сериализация) - Изоляция уровня Serializable обеспечивает беспрепятственный доступ к базе данных транзакциям с SELECT запросами. Но для транзакций с запросами UPDATE и DELETE, уровень изоляции Serializable не допускает модификации одной и той же строки в рамках разных транзакций. При изоляции такого уровня все транзакции обрабатываются так, как будто они все запущены последовательно (одна за другой). Если две одновременные транзакции попытаются обновить одну и туже строку, то это будет не возможно. В таком случае PostgreSQL принудит транзакцию, вторую, да и все последующие, что пытались изменить строку к отмене (откату — ROLLBACK). Фактически этот режим изоляции работает так же, как и Repeatable Read, только он дополнительно отслеживает условия, при которых результат параллельно выполняемых сериализуемых транзакций может не согласовываться с результатом этих же транзакций, выполняемых по очереди.

Ещё один феномен:
**Phantom read (Фантомное чтение)** - Транзакция повторно выполняет запрос, возвращающий набор строк для некоторого условия, и обнаруживает, что набор строк, удовлетворяющих условию, изменился из-за транзакции, завершившейся за это время.

Уровень изоляции транзакций задается командой `BEGIN TRANSACTION LEVEL`.

### 1.3 Расшииения

pgcrypto - расширение PostgreSQL для криптографии.

```sql
create extension if not exists pgcrypto;
```

Создадим таблицу, где номер билета будет храниться в зашифрованном виде. Для шифрования
значений столбца используем функцию `pgp_sym_encrypt`:

```sql
create table tickets_small_encrypted as (
	select pgp_sym_encrypt(ticket_uuid, 'my_very_secret_key') as enc_ticket_uuid,
	aircompany,
	fnum,
	passenger_name,
	departure_date
	from tickets_small
);
```

Дешифрование производится следующим образом с помощью функции `pgp_sym_decrypt`:
```sql
select pgp_sym_decrypt(enc_ticket_uuid::bytea, 'my_very_secret_key') from tickets_small_encrypted where passenger_name = 'Eric Owens';
```

Расширения `pg_bigm` и `pg_trgm` я использовал выше для индексирования колонок flight_number и passenger_name соотвественно.