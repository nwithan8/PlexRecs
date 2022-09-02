from typing import List

from sqlalchemy import VARCHAR, Column, Integer, String, BigInteger, Boolean, func
from sqlalchemy.ext.declarative import declarative_base

import databases.base as db

Base = declarative_base()


class ExternalIDs(Base):
    __tablename__ = 'external_ids'
    ID = Column(Integer, primary_key=True, autoincrement=True)
    ContentID = Column(Integer, nullable=False)
    ExternalID = Column(VARCHAR(500), nullable=False)

    @db.none_as_null
    def __init__(self, content_id: int = None, external_id: str = None, **kwargs):
        self.ContentID = content_id or kwargs.get('ContentID')
        self.ExternalID = external_id or kwargs.get('ExternalID')


class Content(Base):
    __tablename__ = 'content'
    ID = Column(Integer, primary_key=True, autoincrement=True)
    Title = Column(String(1000), nullable=False)
    Year = Column(Integer)
    RatingKey = Column(BigInteger)
    LibraryID = Column(Integer, nullable=False)
    MediaType = Column(String(100), nullable=False)
    OnPlex = Column(Boolean)

    @db.none_as_null
    def __init__(self, title: str = None, year: int = None, rating_key: int = None, library_section_id: int = None,
                 media_type: str = None, on_plex: bool = None, **kwargs):
        self.Title = title or kwargs.get('Title')
        self.Year = year or kwargs.get('Year')
        self.RatingKey = rating_key or kwargs.get('RatingKey')
        self.LibraryID = library_section_id or kwargs.get('LibraryID')
        self.MediaType = media_type or kwargs.get('MediaType')
        self.OnPlex = on_plex or kwargs.get('OnPlex')


class Libraries(Base):
    __tablename__ = 'libraries'
    ID = Column(Integer, primary_key=True, autoincrement=True)
    PlexID = Column(Integer, nullable=False)
    Name = Column(String(500))

    @db.none_as_null
    def __init__(self, name: str = None, plex_id: int = None, **kwargs):
        self.Name = name or kwargs.get('Name')
        self.PlexID = plex_id or kwargs.get('PlexID')


class PlexContentDatabase(db.SQLAlchemyDatabase):
    def __init__(self,
                 sqlite_file: str):
        super().__init__(sqlite_file=sqlite_file)
        Content.__table__.create(bind=self.engine, checkfirst=True)
        ExternalIDs.__table__.create(bind=self.engine, checkfirst=True)
        Libraries.__table__.create(bind=self.engine, checkfirst=True)

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
            # will always reset the external ids during refresh
            self.set_external_ids_for_content(content=content, external_ids=external_ids)

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

    def delete_content(self, content: Content = None, content_id: int = None):
        """
        Delete a content item

        :param content:
        :param content_id:
        :return:
        """
        content_id = content_id or content.ID
        self.delete_external_ids_for_content(content_id=content_id)
        if content:
            content.delete()
        else:
            self.session.query(Content).filter(Content.ID == content_id).delete()
        self.commit()

    def get_external_ids_for_content(self, content: Content = None, content_id: int = None):
        """
        Get all external IDs for a content item

        :param content:
        :param content_id:
        :return:
        """
        content_id = content_id or content.ID
        return self.get_all_by_filters(ExternalIDs, ContentID=content_id)

    def set_external_ids_for_content(self, content: Content = None, content_id: int = None,
                                     external_ids: List[str] = None):
        """
        Set all external IDs for a content item

        :param content:
        :param content_id:
        :param external_ids:
        :return:
        """
        content_id = content_id or content.ID
        self.delete_external_ids_for_content(content_id=content_id)
        for external_id in external_ids:
            external_ids_object = ExternalIDs(content_id=content_id, external_id=external_id)
            self.session.add(external_ids_object)
        self.commit()

    def delete_external_ids_for_content(self, content: Content = None, content_id: int = None):
        """
        Delete all external IDs for a content item

        :param content:
        :param content_id:
        :return:
        """
        content_id = content_id or content.ID
        self.session.query(ExternalIDs) \
            .filter(ExternalIDs.ContentID == content_id).delete()
        self.commit()

    def get_random_contents_for_library(self, library_section_id: int, count: int = 1):
        """
        Get random content for a library section

        :param library_section_id:
        :param count:
        :return:
        """
        return self.session.query(Content). \
            filter_by(LibraryID=library_section_id).order_by(func.random()).limit(count).all()

    def get_random_contents_of_type(self, media_type: str, count: int = 1):
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
