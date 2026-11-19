import os
import shutil
import tempfile


def before_all(context):
    context.tmp = tempfile.mkdtemp()
    context.specs = {}


def before_scenario(context, scenario):
    context.codes = []
    context.bodies = []


def after_all(context):
    shutil.rmtree(context.tmp, ignore_errors=True)
