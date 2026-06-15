from backend.database import get_conn


NAMES = {
    "sina": "\u65b0\u6d6a\u8d22\u7ecf",
    "eastmoney": "\u4e1c\u65b9\u8d22\u5bcc",
    "guba": "\u4e1c\u65b9\u8d22\u5bcc\u80a1\u5427",
    "cninfo": "\u5de8\u6f6e\u8d44\u8baf\u516c\u544a",
    "sample": "\u5b9e\u9a8c\u6837\u672c",
    "caixin": "\u8d22\u65b0\u7f51",
    "ths": "\u540c\u82b1\u987a",
}


def main():
    conn = get_conn()
    cur = conn.cursor()
    rules = [
        (NAMES["sina"], "(url LIKE %s OR url LIKE %s)", ["%sina.com.cn%", "%sinajs%"]),
        (NAMES["guba"], "url LIKE %s", ["%guba.eastmoney.com%"]),
        (NAMES["cninfo"], "url LIKE %s", ["%cninfo.com.cn%"]),
        (NAMES["eastmoney"], "(url LIKE %s AND url NOT LIKE %s)", ["%eastmoney.com%", "%guba.eastmoney.com%"]),
        (NAMES["sample"], "url LIKE %s", ["sample://%"]),
        (NAMES["caixin"], "url LIKE %s", ["%caixin.com%"]),
        (NAMES["ths"], "url LIKE %s", ["%10jqka.com.cn%"]),
    ]
    for source, condition, params in rules:
        cur.execute(f"UPDATE news SET source=%s WHERE {condition}", [source] + params)
        print(source, cur.rowcount)
    conn.commit()
    cur.execute("SELECT source, COUNT(*) FROM news GROUP BY source ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(row)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
