from functools import wraps
from typing import List

from sqlalchemy import create_engine, MetaData, null
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Query


def none_as_null(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        """
        Replace None as null()
        """
        func(self, *args, **kwargs)
        for k, v in self.__dict__.items():
            if v is None:
                setattr(self, k, null())

    return wrapper


def map_attributes(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        """
        Map kwargs to class attributes
        """
        func(self, *args, **kwargs)
        for k, v in kwargs.items():
            if getattr(self, k):
                setattr(self, k, v)

    return wrapper


def false_if_error(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        """
        Return False if error encountered
        """
        try:
            return func(self, *args, **kwargs)
        except:
            return False

    return wrapper


class SQLAlchemyDatabase:
    def __init__(self,
                 sqlite_file: str):
        self.sqlite_file = sqlite_file

        self.engine = None
        self.base = None
        self.meta = None
        self.session = None

        self.url = f'sqlite:///{sqlite_file}'

        self.setup()

    def commit(self):
        self.session.commit()

    def close(self):
        self.session.close()

    def setup(self):
        if not self.url:
            return

        self.engine = create_engine(self.url)

        if not self.engine:
            return

        if not database_exists(self.engine.url):
            create_database(self.engine.url)

        self.base = declarative_base(bind=self.engine)
        self.meta = MetaData()
        self.meta.create_all(self.engine)

        session = sessionmaker()
        session.configure(bind=self.engine)
        self.session = session()

    def get_first_entry(self, table_schema):
        return self.session.query(table_schema).first()

    def get_all_entries(self, table_schema):
        return self.session.query(table_schema).all()

    def get_all_by_filters(self, table, **kwargs):
        query = self.session.query(table)
        for k, v in kwargs.items():
            if v is not None:
                query = query.filter(k == v)
        return query.all()

    def get_attribute_from_first_entry(self, table_schema, field_name):
        entry = self.get_first_entry(table_schema=table_schema)
        return getattr(entry, field_name, None)

    def set_attribute_of_first_entry(self, table_schema, field_name, field_value) -> bool:
        entry = self.get_first_entry(table_schema=table_schema)
        if not entry:
            entry = self.create_entry(table_schema, **{field_name: field_value})
        return self.update_entry_single_field(entry, field_name, field_value)

    @false_if_error
    def create_entry(self, table_schema, **kwargs):
        entry = table_schema(**kwargs)
        self.session.add(entry)
        self.commit()
        return entry

    @false_if_error
    def create_entry_if_does_not_exist(self, table_schema, fields_to_check: List[str], **kwargs):
        filters = {k: v for k, v in kwargs.items() if k in fields_to_check}
        entries = self.get_all_by_filters(table_schema=table_schema, **filters)
        if not entries:
            return self.create_entry(table_schema=table_schema, **kwargs)
        return entries[0]

    @false_if_error
    def update_entry_single_field(self, entry, field_name, field_value) -> bool:
        setattr(entry, field_name, field_value)
        self.commit()
        return True

    @false_if_error
    def update_entry_multiple_fields(self, entry, **kwargs) -> bool:
        for field, value in kwargs.items():
            setattr(entry, field, value)
        self.commit()
        return True


class CustomTable:
    def __init__(self):
        self._ignore = []
