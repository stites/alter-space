import os
import json
import logging
from time import sleep
import requests
from flask import jsonify, Blueprint, request, render_template, make_response, url_for, send_file
from config import config, light_presets, sound_presets

from backend import tasks

from helpers import get_sound_paths

logger = logging.getLogger()

backend_app = Blueprint('backend', __name__)
tsk = Blueprint('backend.tasks', __name__)

throttle_time = 0.3


def throttle(throttle_duration=throttle_time):
    sleep(throttle_duration)


@tsk.route('/task/start/<task_name>', methods=['POST'])
@backend_app.route('/task/start/<task_name>', methods=['POST'])
def start_task(task_name):
    """start task, return task_id"""

    logger.info('start task... %s' % task_name)
    if task_name == "wait":
        sleep_time = int(request.form.get('sleep_time', 5))
        data = {"sleep_time": sleep_time}
        task = tasks.wait_task.apply_async(kwargs=data)
    elif task_name == "breathe":
        light_id = request.form.get('light_id')
        breathe_type = request.form.get('breathe_type')
        data = {'light_id': light_id, 'breathe_type': breathe_type}
        task = tasks.breathe_task.apply_async(kwargs=data)
    elif task_name == "chase":
        light_id = request.form.get('light_id')
        data = {"light_id": light_id}
        task = tasks.chase_task.apply_async(kwargs=data)
    else:
        error_message = "Task with name %s was not found" % task_name
        return make_response(error_message, 404)

    return jsonify({
        'task_id': task.id,
        'state': task.state,
        'data': data}), 202


@tsk.route('/task/stop/<task_name>', methods=['POST'])
@backend_app.route('/task/stop/<task_name>', methods=['POST'])
def stop_task(task_name):
    """start task, return task_id"""

    task_id = request.form.get('task_id')
    logging.info('stop task...%s' % task_id)

    task = tasks.stop_task.delay(task_name, task_id)
    data = {"id": task_id}

    return jsonify({
        'task_id': task.id,
        'state': task.state,
        'data': data}), 202


@tsk.route('/task/<task_name>/<task_id>', methods=['GET'])
@backend_app.route('/task/<task_name>/<task_id>', methods=['GET'])
def check_task(task_name, task_id):
    """return task state"""
    if task_name == "wait":
        task = tasks.wait_task.AsyncResult(task_id)
    elif task_name == "breathe":
        task = tasks.breathe_task.AsyncResult(task_id)
    elif task_name == "chase":
        task = tasks.chase_task.AsyncResult(task_id)
    output = {'task_id': task.id, 'state': task.state}
    if task.state == 'SUCCESS':
        output.update({'result': task.result})
    return jsonify(output)


@backend_app.route('/', methods=['GET'])
def index():
    return render_template("index.html")


@backend_app.route("/sounds")
def sounds():
    nature_paths = get_sound_paths('nature')
    urban_paths = get_sound_paths('urban')
    abstract_paths = get_sound_paths('abstract')
    return jsonify({
        "nature": nature_paths,
        "urban": urban_paths,
        "abstract": abstract_paths
    })


@backend_app.route("/sounds/<sound_type>")
def sounds_of_type(sound_type):
    paths = get_sound_paths(sound_type)
    return jsonify(paths)


@backend_app.route("/sounds/<sound_type>/<sound_name>")
def sound_file(sound_type, sound_name):
    sound_dir = os.path.join(config.DIR, "sounds")
    single_file = os.path.join(sound_dir, "%s/%s" % (sound_type, sound_name))
    return send_file(single_file)


@backend_app.route("/activities")
def activities():
    return jsonify(config.ACTIVITIES)


@backend_app.route("/activity/<activity>")
def get_activity_presets(activity):
    presets = {
        "sound": sound_presets.presets[activity],
        "light": light_presets.presets[activity],
    }
    return jsonify(presets)


# LIGHT CONTROLS
@backend_app.route("/lights/effects/<effect_type>", methods=['POST'])
def toggle_effect(effect_type):
    effect_status = request.form.get('effect')
    effect_status = True if effect_status == "true" else False
    data = {"light_id": request.form.get('light_id')}
    if effect_type == "breathe":
        data["breathe_type"] = request.form.get("breathe_type")
    if effect_status:
        results = requests.post(url_for("backend.start_task", task_name=effect_type, _external=True), data=data)
    else:
        data["task_id"] = request.form.get('task_id')
        results = requests.post(url_for("backend.stop_task", task_name=effect_type, _external=True), data=data)
    throttle()
    return jsonify(results.json())


@backend_app.route("/lights/colors")
def get_color_presets():
    colors = light_presets.colors
    return jsonify(colors)


@backend_app.route("/lights/set", methods=['POST'])
def set_light():
    light_id = request.form.get('id')
    colors = json.loads(request.form.get('colors'))['color_data']
    dim_value = request.form.get('bright', 100)

    try:
        tasks.light_task.apply_async(kwargs={'light_id': light_id, 'colors': colors, 'dim_value': dim_value})
        throttle()
        return "ok"
    except Exception as e:
        raise Exception(e, "Something went wrong!")


@backend_app.route("/lights/dim", methods=['POST'])
def set_dim():
    light_id = request.form.get('id')
    dim_level = request.form.get('bright', 100)
    try:
        tasks.dim_task.apply_async(kwargs={'light_id': light_id, 'dim_value': dim_level})
        throttle()
        return "ok"
    except Exception as e:
        raise Exception(e, "Something went wrong!")
