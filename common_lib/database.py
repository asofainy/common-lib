
import logging
import os
import sqlalchemy

from sqlalchemy.exc import IntegrityError

from fastapi import Query, Path, HTTPException, Depends
from typing import Annotated

# pylint: disable=E0401
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlmodel import create_engine, SQLModel, Session, select
from sqlmodel import delete as sm_delete
# pylint: enable=E0401

from common_lib.config.client import ConfigClient

logger = logging.getLogger('service')

if os.getenv("APP_ENV") == "dev" :
    URL = "sqlite:///dev.db"
    connect_args = {"check_same_thread": False}

else :
    
    DB_USER = ConfigClient.get_property(key="DB_USER", section="POSTGRES")
    DB_PASSWORD = ConfigClient.get_property(key="DB_PASSWORD", section="POSTGRES")
    DB_HOST = ConfigClient.get_property(key="DB_HOST", section="POSTGRES")
    DB_PORT = ConfigClient.get_property(key="DB_PORT", section="POSTGRES")
    DB_NAME = ConfigClient.get_property(key="DB_NAME", section="POSTGRES")
    URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    connect_args = None

#def create_db_and_tables():
#    global ENGINE

logger.info("Creating database enging : %s", URL)
ENGINE = create_engine(URL)

#SQLAlchemyInstrumentor().instrument(engine=ENGINE)

SQLModel.metadata.create_all(ENGINE)

def get_session():
    global ENGINE
    with Session(ENGINE) as session:
        yield session

def handle_exception(e, session):
    logger.error("Catched exception of type : %s", e.__class__.__name__)
    if e.__class__.__name__ in {'IntegrityError', 'PendingRollbackError'}:
        logger.error(e)
        logger.warning("Performing a session rollback")
        session.rollback()
    else:
        logger.error(type(e))
        session.rollback()
    raise e

def add(item, session = next(get_session())):
    r = None
    try:
        session.add(item)
        session.commit()
        session.refresh(item)
        r = item
    except Exception as e:
        handle_exception(e, session)
    return r

def add_all(items, session = None):
    if not session :
        session = next(get_session())
    r = None
    try:
        r = session.add_all(items)
        session.commit()
    except Exception as e:
        handle_exception(e, session)
    return r

def select_all(model_class, offset = None, limit = None, session = None): 
    #with Session(ENGINE) as session:
    if not session :
        session = next(get_session())
    r = None
    try:
        r = session.exec(select(model_class).offset(offset).limit(limit)).all()
    except Exception as e:
        handle_exception(e, session)
    return r

def select_all_by_date(model_class, by_date, offset = None, limit = None, session = None): 
    #with Session(ENGINE) as session:
    if not session :
        session = next(get_session())
    r = None
    try:
        if 'DESC' in by_date :
            r = session.exec(select(model_class).offset(offset).limit(limit).order_by(model_class.date_operation.desc())).all()
        else :
            r = session.exec(select(model_class).offset(offset).limit(limit).order_by(model_class.date_operation)).all()    
    except Exception as e:
        handle_exception(e, session)
    return r

def get(object_id, model_class, session = next(get_session())):
    r = None
    try:
        r = session.get(model_class, object_id)
    except Exception as e:
        handle_exception(e, session)
    return r

def get_by_key(key, value, model_class, session):
    import model
    model_class_name = model_class.__tablename__
    if session is None:
        session = next(get_session())
    r = None
    try:
        r = session.exec(select(model_class).where(eval(f"model.{model_class_name}."+ f"{model_class_name}.{key}".capitalize()) == value)).all()
    except Exception as e:
        handle_exception(e, session)
    return r

def delete_by_key(key, value, model_class, session):
    import model
    model_class_name = model_class.__tablename__
    if session is None:
        session = next(get_session())
    r = None
    try:
        if key is None:
            logging.warning("No key specified deleting all entries !")
            r = session.exec(sm_delete(model_class))
        else :
            r = session.exec(sm_delete(model_class).where(eval(f"model.{model_class_name}."+ f"{model_class_name}.{key}".capitalize()) == value))
        session.commit()
    except Exception as e:
        handle_exception(e, session)
    return r

def update(object_id, model_class, model_object, session = next(get_session())):
    try:
        r = session.get(object_id, model_class,)
        if r :
            r.sqlmodel_update(model_object)
            session.add( r)
    except Exception as e:
        handle_exception(e, session)
    return r

def delete(object_id, model_class, session = next(get_session()) ):
    try:
        r = session.get(model_class, object_id)
        if r:
            session.delete(r)
            session.commit()
            #d = session.exec(delete(TransactionModule.Transaction).where(TransactionModule.Transaction.account_id == account.id))
            #logger.warning('Deleted %s transactions for account: %s', str(d.rowcount))
    except Exception as e:
        handle_exception(e, session)
    return r


def commit(session):
    try:
        session.commit()
    except Exception as e:
        handle_exception(e, session)