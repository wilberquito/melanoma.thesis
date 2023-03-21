import os
from typing import List, Union, ValuesView
import json

import fastapi
import starlette.status as status
from fastapi import (BackgroundTasks, FastAPI, File, HTTPException, Request,
                     UploadFile)

from modular.vision import mk_prediction, get_supported_models
from modular.utility import mk_temporal_task, save_file_to_disk, is_uploaded_image_sanitized, read_yaml

from pathlib import Path

conf = read_yaml('./api.conf.yml')

app = FastAPI()

@app.get("/")
def home(request: Request):
    return fastapi.responses.RedirectResponse('/docs', status_code=status.HTTP_302_FOUND)


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.post("/predict")
async def predict(file: UploadFile = File(...), model_id='vicorobot.efficientnet_b3'):

    # Is the uploaded file and image?
    __sanitize_file(file)

    # New temporal task path
    task_id: Path = mk_temporal_task(parent_path=conf['TEMPORALTASKS'])

    # Save image inside the task folder
    save_file_to_disk(parent_dir=task_id,
                      file=file,
                      save_as=str(file.filename))

    # Make prediction from task asyncronous
    await mk_prediction(model_id=model_id,
                        task_id=task_id)

    # Returns the unique id of the task generated to consult the prediction late
    return {
        'uuid_task': task_id.parts[-1]
    }

def __sanitize_file(file):
    """
    Check if the file is jpeg or png content type, if not throws and exception
    """
    if not is_uploaded_image_sanitized(file):
        raise HTTPException(status_code=400, detail='Content type - %s - not supported' % (file.content_type))


@app.post("/predict_bulk")
async def predict_bulk(request: Request,
                       bg_tasks: BackgroundTasks,
                       model_id='vicorobot.efficientnet_b3'):

    '''
    Function that saves into a unique folder the jar of images from the request.
    So you can consume these images, the uuid of the folder is returned

    Returns
    -------
    task_id: str
        folder where the images where saved

    num_files: int
        number of images saved
    '''
    # Takes the files from the form request
    files = await request.form()

    # Creates a new task
    task_id: Path = mk_temporal_task(parent_path=conf['TEMPORALTASKS'])

    # Sanitize each image and save inside the task
    for file in files.values():

        # Check the state of the file
        __sanitize_file(file)

        # Save image inside the task folder
        save_file_to_disk(parent_dir=task_id,
                          file=file,
                          save_as=str(file.filename))

    bg_tasks.add_task(mk_prediction,
                      model_id=model_id,
                      task_id=task_id)

    return {
        "task_id": task_id,
        "num_files": len(files)
    }


@app.get("/predict_packet_output/{task_id}")
async def predict_images_pack_output(task_id: int):
    '''
    Takes the prediction from task_id folder and returns it.
    May happen that the prediction request and the prediction output
    where faster than the prediction process itself and may not found the prediction,
    in this case, I recommend to consume this end point
    '''
    for file_ in os.listdir(task_id):
        if file_.endswith((".csv")):
            # TODO: transform csv to dict object using DataFrame and return it
            return {
                "task_id": task_id,
                "output": "work in progress"
            }
    return HTTPException(status_code=500, detail='Prediction not found for - %s - task_id' % (task_id))


@app.get("/supported_models")
async def supported_models():
    """
    Description
    ----------
    returns the name of the available models to make prediction of skin cancers
    """
    return {
        "models": get_supported_models()
    }
