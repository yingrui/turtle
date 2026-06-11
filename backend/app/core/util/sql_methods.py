from sqlalchemy.dialects.postgresql import insert


def insert_or_update(table, conn, keys, data_iter):
    data = [dict(zip(keys, row)) for row in data_iter]
    if not data:
        return 0
    insert_stmt = insert(table.table).values(data)
    pk_columns = [c.name for c in table.table.primary_key]
    update_dict = {
        c.name: insert_stmt.excluded[c.name]
        for c in table.table.columns
        if c.name not in pk_columns
    }
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=pk_columns,
        set_=update_dict,
    )
    result = conn.execute(upsert_stmt)
    return result.rowcount
