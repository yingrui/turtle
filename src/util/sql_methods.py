from sqlalchemy.dialects.mysql import insert


def insert_or_update(table, conn, keys, data_iter):
    insert_stmt = insert(table.table).values(list(data_iter))
    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(insert_stmt.inserted)
    result = conn.execute(on_duplicate_key_stmt)
    return result.rowcount
