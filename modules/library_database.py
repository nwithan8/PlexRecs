from typing import List

from sqlalchemy import Column, Integer, String, BigInteger, Boolean, func
from sqlalchemy.ext.declarative import declarative_base

import databases.base as db

Base = declarative_base()


class ExternalIDs(Base):
    __tablename__ = 'external_ids'
    ItemID = Column(Integer, primary_key=True)
    ExternalID = Column(String(255))


class Content(Base):
    __tablename__ = 'content'
    ID = Column(Integer, primary_key=True)
    Title = Column(String(1000))
    Year = Column(Integer)
    RatingKey = Column(BigInteger)
    LibraryID = Column(Integer)
    MediaType = Column(String(100))
    OnPlex = Column(Boolean)

    @db.none_as_null
    def __init__(self, title: str, year: int, rating_key: int, library_section_id: int, media_type: str, on_plex: bool):
        self.Title = title
        self.Year = year
        self.RatingKey = rating_key
        self.LibraryID = library_section_id
        self.MediaType = media_type
        self.OnPlex = on_plex

    @property
    def external_ids(self) -> List[ExternalIDs]:
        return self.session.query(ExternalIDs).filter_by(ItemID=self.ID).all()

    def add_external_ids(self, external_ids: List[str]):
        for external_id in external_ids:
            self.session.add(ExternalIDs(ItemID=self.ID, ExternalID=external_id))
        self.session.commit()

    def delete(self):
        for external_id in self.external_ids:
            self.session.delete(external_id)
        self.session.delete(self)


class Libraries(Base):
    __tablename__ = 'libraries'
    ID = Column(Integer, primary_key=True)
    PlexID = Column(Integer, nullable=False)
    Name = Column(String(200))

    def __init__(self, name: str, plex_id: int):
        self.Name = name
        self.PlexID = plex_id

    @property
    def content(self) -> List[Content]:
        return self.session.query(Content).filter_by(Content.LibraryID == self.PlexID).all()

    def get_random_content(self, count: int) -> List[Content]:
        return self.session.query(Content). \
            filter(Content.LibraryID == self.PlexID). \
            order_by(func.random()). \
            limit(count).all()


class PlexContentDatabase(db.SQLAlchemyDatabase):
    def __init__(self,
                 sqlite_file: str):
        super().__init__(sqlite_file=sqlite_file)
        Content.__table__.create(bind=self.engine, checkfirst=True)
        ExternalIDs.__table__.create(bind=self.engine, checkfirst=True)

    def add_library(self, name: str, plex_id: int):
        """
        Add a library to the database
        :param name:
        :param plex_id:
        :return:
        """
        library = self.create_entry_if_does_not_exist(table_schema=Libraries, fields_to_check=["PlexID"], Name=name,
                                                      PlexID=plex_id)

    def add_content(self, title: str, year: int, rating_key: int, library_section_id: int, media_type: str,
                    external_ids: List[str] = None):
        """
        Add a new content item
        :param external_ids:
        :param title:
        :param year:
        :param rating_key:
        :param library_section_id:
        :param media_type:
        :return:
        """
        content = self.create_entry_if_does_not_exist(table_schema=Content, fields_to_check=["RatingKey"],
                                                      Title=title, Year=year, RatingKey=rating_key,
                                                      LibraryID=library_section_id,
                                                      MediaType=media_type, OnPlex=True)
        if external_ids:
            content.add_external_ids(external_ids)

    def get_content(self, content_id: int = None, title: str = None, year: int = None, library_section_id: int = None,
                    media_type: str = None):
        """
        Get all content items matching the given parameters
        :param content_id:
        :param title:
        :param year:
        :param library_section_id:
        :param media_type:
        :return:
        """
        filters = {
            'ID': content_id,
            'Title': title,
            'Year': year,
            'LibrarySectionID': library_section_id,
            'MediaType': media_type
        }
        return self.get_all_by_filters(Content, **filters)

    def update_plex_status_for_content(self, content_id: int, plex_status: bool):
        """
        Update the Plex status for a content item
        :param content_id:
        :param plex_status:
        :return:
        """
        content = self.get_content(content_id=content_id)
        content.OnPlex = plex_status
        self.commit()

    def get_random_content_for_library(self, library_section_id: int, count: int = 1):
        """
        Get random content for a library section
        :param library_section_id:
        :param count:
        :return:
        """
        return self.session.query(Libraries).filter_by(PlexID=library_section_id).one().get_random_content(count=count)

    def get_random_content_of_type(self, media_type: str, count: int = 1):
        """
        Get random content of a given type
        :param media_type:
        :param count:
        :return:
        """
        return self.session.query(Content).filter_by(MediaType=media_type).order_by(func.random()).limit(count).all()

    def purge(self):
        """
        Purge all content that is not on Plex
        :return:
        """
        for content in self.session.query(Content).filter(Content.OnPlex is False).all():
            content.delete()
        self.commit()
