'''
    Module to manage server related actions
'''
from common_lib.config.client import ConfigClient
from common_lib.errors import ServiceError
import logging
from enum import Enum
import uvicorn
import requests
from os.path import join
from pathlib import Path
import json as JSON
import os


from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)

from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import ResponseValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import PlainTextResponse
from fastapi.responses import JSONResponse
from fastapi import FastAPI


FILE_MANAGER_URL = f'http://{ConfigClient.get_property(key="FILE_MANAGER_HOST", section="MICROSERVICE")}:{ConfigClient.get_property(key="FILE_MANAGER_PORT", section="MICROSERVICE")}'
CRYPTOCURRENCY_MANAGER_URL = f'http://{ConfigClient.get_property(key="CRYPTOCURRENCY_MANAGER_HOST", section="MICROSERVICE")}:{ConfigClient.get_property(key="CRYPTOCURRENCY_MANAGER_PORT", section="MICROSERVICE")}'
BINANCE_CONNECTOR_URL = f'http://{ConfigClient.get_property(key="BINANCE_CONNECTOR_HOST", section="MICROSERVICE")}:{ConfigClient.get_property(key="BINANCE_CONNECTOR_PORT", section="MICROSERVICE")}'

app = None

logger = logging.getLogger('service')

class RequestTypeEnum(Enum):
    '''
        HTTP request type enumeratoin
    '''
    GET = 'get'
    POST = 'post'




def get_app(app_name, lifespan = None):

    global app

    if app is not None :
        return app

    else:
        
        version = ConfigClient.get_property(key="APP_VERSION", section="DEFAULT")
        summary = ConfigClient.get_property(key="APP_SUMMARY", section="DEFAULT")

        base_path = ConfigClient.get_base_path()
        with open(base_path / ConfigClient.get_property(key="APP_DESCRIPTION_FILE", section="DEFAULT"), 'r', encoding='utf-8') as file:
            description = "".join(file.readlines()).replace('\n','')

        with open(base_path / ConfigClient.get_property(key="APP_TAG_METADATA_FILE", section="DEFAULT"), 'r', encoding='utf-8') as file:
            tags_metadata = JSON.loads("".join(file.readlines()).replace('\n',''))

        app = FastAPI(
            lifespan = lifespan,
            title = app_name,
            description = description,
            version = version ,
            summary = summary ,
            openapi_tags = tags_metadata,
            terms_of_service="http://example.com/terms/",
            contact={
                "name": "Deadpoolio the Amazing",
                "url": "http://x-force.example.com/contact/",
                "email": "dp@x-force.example.com",
            },
            license_info={
                "name": "Apache 2.0",
                "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
            }
        )

        override_exception_handlers(app)

        return app

def start_uvicorn():
    '''
        Start uvicorn server
    '''

    host = ConfigClient.get_property(key="HOST", section="UVICORN")
    port = int(ConfigClient.get_property(key="PORT", section="UVICORN"))
    #workers = int(ConfigClient.get_property(key="WORKERS", section="UVICORN"))

    workers = 1
    if os.getenv('UVICORN_WORKERS') :
        workers = int(os.getenv('UVICORN_WORKERS'))

    reload = False
    if os.getenv("APP_ENV") == 'dev' :
        reload = True

    if workers > 1 :
        reload = False

    logger.info("Starting uvicorn server [env= %s, workers = %s, reload = %s]", os.getenv('APP_ENV'), workers, reload)
    #try :
    uvicorn.run( 'main:app', host=host, port=port, workers=workers, reload=reload)
    #except Exception as e :
    #    logger.error(e)
    #    exit(-5)
    #    #raise(e)

def send_http_request (
    request_type: RequestTypeEnum, url: str ,
    headers: dict = None, params: dict = None, data: dict = None,
    timeout: int = int(ConfigClient.get_property(key="TIMEOUT", section="SERVER"))):
    '''
        Control and send HTTP requests
    '''
    response = None
    if request_type == RequestTypeEnum.GET :
        response = requests.get(url=url, headers=headers, params=params, data=data, timeout=timeout)

    if request_type == RequestTypeEnum.POST :
        response = requests.post(url=url, headers=headers, params=params, data=data, timeout=timeout)

    #if response.status_code not in [200, 204] :
    try :
        response.raise_for_status()
        #detail = response.json()['detail']
    #except Exception as e :
        #detail = response.text
    except requests.exceptions.HTTPError as e:
        logger.exception(e)
        #HTTPException(status_code=response.status_code,detail=detail)

    return response


def override_exception_handlers(app):

    if ConfigClient.get_property(key="EXCEPTION_HANDLER", section="SERVER") == "on" :
        @app.exception_handler(ServiceError)
        async def service_exception_handler(request, exc: ServiceError):
            logger.exception(exc)
            return JSONResponse(content={"detail": str(exc)}, status_code=exc.status_code)

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            logger.exception(exc)
            return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request, exc: RequestValidationError):
            message = "Validation errors:"
            for error in exc.errors():
                message += f"\nField: {error['loc']}, Error: {error['msg']}"
                logger.error(message)
            return PlainTextResponse(message, status_code=400)

        @app.exception_handler(ResponseValidationError)
        async def validation_exception_handler(request, exc: ResponseValidationError):
            message_user = f"Found {len(exc.errors())} Validation errors, please check logs."
            for error in exc.errors():
                #message.append({"Field" : error['loc'],  "Message": {error['msg']} })
                summary = error['msg']
                detail = ""
                query = ""
                if '\n' in error['msg'] :
                    s = error['msg'].split('\n')
                    summary = s[0]
                    detail = s[1]
                    query = s[3]
                message = """
Location:   {} at {}
Sumary:     {}
Details:    {}
Query:      {}
Input:      {}""".format(error['type'], error['loc'],summary, detail, query,error['input'])

                
                logger.error(message)
                #message.append(error)
            return PlainTextResponse(message_user, status_code=400)
            #return JSONResponse(content = message, status_code = 400)

    #@app.get("/heartbeat", tags=["default"], status_code = 200)
    #def heartbeat() -> dict :
    #    '''
    #        Heartbeat check
    #        ---
    #        Checks the heartbeat of the microservice
    #    '''
    #    return { 'status' : 'ok' }