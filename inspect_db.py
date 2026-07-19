import sqlite3

con = sqlite3.connect(r'd:\Kampus\Lomba\Pidi\Latihan\Hackathon-X-Digdaya\IDX-API\data\database.sqlite')
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()

print("=== TABLES & ROW COUNTS ===")
for t in tables:
    name = t[0]
    count = cur.execute(f'SELECT COUNT(*) FROM [{name}]').fetchone()[0]
    print(f"  {name}: {count} rows")

con.close()
