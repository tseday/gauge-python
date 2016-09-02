import os
import re
import tempfile
from subprocess import call

from getgauge.api import get_step_value


class StepInfo(object):
    def __init__(self, step_text, parsed_step_text, impl, file_name, line_number, has_alias=False):
        self.__step_text, self.__parsed_step_text, self.__impl = step_text, parsed_step_text, impl
        self.__file_name, self.__line_number, self.__has_alias = file_name, line_number, has_alias

    @property
    def step_text(self):
        return self.__step_text

    @property
    def parsed_step_text(self):
        return self.__parsed_step_text

    @property
    def impl(self):
        return self.__impl

    @property
    def has_alias(self):
        return self.__has_alias

    @property
    def file_name(self):
        return self.__file_name

    @property
    def line_number(self):
        return self.__line_number


class _MessagesStore:
    __messages = []

    @staticmethod
    def pending_messages():
        messages = _MessagesStore.__messages
        _MessagesStore.__messages = []
        return messages

    @staticmethod
    def write_message(message):
        _MessagesStore.__messages.append(message)

    @staticmethod
    def clear():
        _MessagesStore.__messages = []


class Registry(object):
    hooks = ['before_step', 'after_step', 'before_scenario', 'after_scenario', 'before_spec', 'after_spec',
             'before_suite', 'after_suite']

    def __init__(self):
        self.__screenshot_provider, self.__steps_map, self.__continue_on_failures = _take_screenshot, {}, {}
        for hook in Registry.hooks:
            self.__def_hook(hook)

    def __def_hook(self, hook):
        def get(self, tags=None):
            return _filter_hooks(tags, getattr(self, '__{}'.format(hook)))

        def add(self, func, tags=None):
            getattr(self, '__{}'.format(hook)).append({'tags': tags, 'func': func})

        setattr(self.__class__, hook, get)
        setattr(self.__class__, 'add_{}'.format(hook), add)
        setattr(self, '__{}'.format(hook), [])

    def add_step(self, step_text, func, file_name, line_number=-1, has_alias=False):
        if not isinstance(step_text, list):
            parsed_step_text = get_step_value(step_text)
            info = StepInfo(step_text, parsed_step_text, func, file_name, line_number, has_alias)
            self.__steps_map.setdefault(parsed_step_text, []).append(info)
            return
        for text in step_text:
            self.add_step(text, func, file_name, line_number, True)

    def steps(self):
        return [value[0].step_text for value in self.__steps_map.values()]

    def is_implemented(self, step_text):
        return self.__steps_map.get(step_text) is not None

    def has_multiple_impls(self, step_text):
        return len(self.__steps_map.get(step_text)) > 1

    def get_info_for(self, step_text):
        info = self.__steps_map.get(step_text)
        return info[0] if info is not None else StepInfo(None, None, None, None, None)

    def get_infos_for(self, step_text):
        return self.__steps_map.get(step_text)

    def set_screenshot_provider(self, func):
        self.__screenshot_provider = func

    def screenshot_provider(self):
        return self.__screenshot_provider

    def continue_on_failure(self, func, exceptions=None):
        self.__continue_on_failures[func] = exceptions or [AssertionError]

    def is_continue_on_failure(self, func, exception):
        if func in self.__continue_on_failures:
            for e in self.__continue_on_failures[func]:
                if issubclass(type(exception), e):
                    return True
        return False

    def clear(self):
        self.__steps_map, self.__continue_on_failures = {}, {}
        for hook in Registry.hooks:
            setattr(self, '__{}'.format(hook), [])


def _filter_hooks(tags, hooks):
    filtered_hooks = []
    for hook in hooks:
        hook_tags = hook['tags']
        if hook_tags is None:
            filtered_hooks.append(hook['func'])
            continue
        for tag in tags:
            hook_tags = hook_tags.replace('<{}>'.format(tag), 'True')
        if eval(re.sub('<[^<]+?>', 'False', hook_tags)):
            filtered_hooks.append(hook['func'])
    return filtered_hooks


def _take_screenshot():
    temp_file = os.path.join(tempfile.gettempdir(), 'screenshot.png')
    call(['gauge_screenshot', temp_file])
    if not os.path.exists(temp_file):
        return str.encode("")
    _file = open(temp_file, 'r+b')
    data = _file.read()
    _file.close()
    return data


registry = Registry()
