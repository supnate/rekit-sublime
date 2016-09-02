#!/usr/bin/python
import os
import sublime
import sublime_plugin
import logging
import functools
import re
import subprocess
import threading

def Window():
  return sublime.active_window()

def main_thread(callback, *args, **kwargs):
  # sublime.set_timeout gets used to send things onto the main thread
  # most sublime.[something] calls need to be on the main thread
  sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

class CommandThread(threading.Thread):
  def __init__(self, command, on_done, working_dir="", shell="", env={}):
    threading.Thread.__init__(self)
    self.command = command
    self.on_done = on_done
    self.working_dir = working_dir
    self.shell = shell
    self.env = os.environ.copy()
    self.env.update(env)

  def run(self):
    si = None
    if hasattr(subprocess, "STARTUPINFO"):
      si = subprocess.STARTUPINFO()
      si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
      #si.wShowWindow = subprocess.SW_HIDE # default
      p = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=si)
      for line in p.stdout.readlines():
        print(line)

    except subprocess.CalledProcessError as e:
      sublime.error_message(str(e))

    except OSError as e:
      if e.errno == 2:
        main_thread(sublime.error_message, "Node binary could not be found in PATH\nConsider using the node_command setting for the Rekit plugin\n\nPATH is: %s" % os.environ['PATH'])
      else:
        raise e

def run_command(command, callback=None, show_status=True, filter_empty_args=True, **kwargs):
  if filter_empty_args:
    command = [arg for arg in command if arg]

  s = sublime.load_settings("Rekit.sublime-settings")

  if command[0] == 'node' and s.get('node_command'):
    command[0] = s.get('node_command')

  if command[0] == 'node' and s.get('node_path'):
    kwargs['env'] = { "NODE_PATH" : str(s.get('node_path')) }

  if command[0] == 'npm' and s.get('npm_command'):
    command[0] = s.get('npm_command')

  thread = CommandThread(command, callback, **kwargs)
  thread.start()

def run_script(path, name, args = []):
  js_file = os.path.join(get_rekit_root(path), 'tools', name + '.js').replace('\\', '/').replace('\\', '/')
  run_command(['node', js_file] + args)

def is_rekit_root(path):
  if path is None:
    return False
  return os.path.exists(os.path.join(path, 'src/features').replace('\\', '/')) \
    and os.path.exists(os.path.join(path, 'tools/templates/Page.js').replace('\\', '/'))

def get_rekit_root(path):
  lastPath = None
  while path != lastPath and not is_rekit_root(path):
    lastPath = path
    path = os.path.dirname(path)
  if lastPath == path:
    return None
  else:
    return path

def get_filename_without_ext(path):
  return re.sub(r'\.\w+', '', os.path.basename(path))

def get_feature_name(path):
  return path.split('src/features/')[1].split('/')[0]

def is_rekit_project(path):
  return get_rekit_root(path) is not None

def is_feature(path):
  return is_rekit_project(path) and os.path.dirname(path) == os.path.join(get_rekit_root(path), 'src/features').replace('\\', '/')

def is_features_folder(path):
  return is_rekit_project(path) and path == os.path.join(get_rekit_root(path), 'src/features').replace('\\', '/')

def is_feature_element(path):
  return is_rekit_project(path) and re.search(r'src/features/\w+', os.path.dirname(path)) is not None;

def is_page(path):
  return False

def is_component(path):
  if not is_rekit_project(path):
    return False
  filename = os.path.basename(path)

  if re.search(r'^([A-Z]+[a-z0-9]+)+\.', filename) is None:
    return False

  if re.search(r'\.js$|\.less$|\.scss$|\.css$', filename) is None:
    return False

  path = re.sub(r'\.less$|\.scss$|\.css$', '.js', path)
  if not os.path.exists(path):
    return False

  text = open(path, 'r').read()
  if re.search('class ' + get_filename_without_ext(filename) + ' extends', text, re.MULTILINE) is None:
    return False

  if re.search('export default connect\(', text, re.MULTILINE) is not None:
    return False

  return True

def is_page(path):
  if not is_rekit_project(path):
    return False
  filename = os.path.basename(path)

  if re.search(r'^([A-Z]+[a-z0-9]+)+\.', filename) is None:
    return False

  if re.search(r'\.js$|\.less$|\.scss$|\.css$', filename) is None:
    return False

  path = re.sub(r'\.less$|\.scss$|\.css$', '.js', path)
  if not os.path.exists(path):
    return False

  text = open(path, 'r').read()
  if re.search('class ' + get_filename_without_ext(filename) + ' extends', text, re.MULTILINE) is None:
    return False

  if re.search('export default connect\(', text, re.MULTILINE) is None:
    return False

  return True

def is_actions(path):
  return os.path.basename(path) == 'actions.js' \
    and is_rekit_project(path) \
    and is_feature(os.path.dirname(path))

def is_reducer(path):
  return os.path.basename(path) == 'reducer.js' \
    and is_rekit_project(path) \
    and is_feature(os.path.dirname(path))


def is_other():
  return True

def get_path(paths):
  return paths[0].replace('\\', '/')

class AddFeatureCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_feature', [name])
    # run_script(get_path(paths), 'add_action', ['%s/%s-test-action' % (name, name)])
    # run_script(get_path(paths), 'add_page', ['%s/default-page' % name])

  def is_visible(self, paths = []):
    return is_features_folder(get_path(paths))

class RemoveFeatureCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    feature_name = get_feature_name(get_path(paths))
    if sublime.ok_cancel_dialog('Remove Feature: %s?' % feature_name, 'Remove'):
      run_script(get_path(paths), 'rm_feature', [feature_name])

  def is_visible(self, paths = []):
    return is_feature(get_path(paths))

class AddComponentCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name/component name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_component', name.split(' '))

  def is_visible(self, paths = []):
    return is_feature(get_path(paths))

class RemoveComponentCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    feature_name = get_feature_name(get_path(paths))
    component_name = get_filename_without_ext(get_path(paths))
    if sublime.ok_cancel_dialog('Remove Component: %s/%s?' % (feature_name, component_name), 'Remove'):
      Window().run_command('close')
      run_script(get_path(paths), 'rm_component', ['%s/%s' % (feature_name, component_name)])
  def is_visible(self, paths = []):
    return is_component(get_path(paths))

class AddPageCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name/page name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_page', name.split(' '))

  def is_visible(self, paths = []):
    return is_feature(get_path(paths))

class RemovePageCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    feature_name = get_feature_name(get_path(paths))
    page_name = get_filename_without_ext(get_path(paths))
    if sublime.ok_cancel_dialog('Remove Page: %s/%s?' % (feature_name, page_name), 'Remove'):
      Window().run_command('close')
      run_script(get_path(paths), 'rm_page', ['%s/%s' % (feature_name, page_name)])
  def is_visible(self, paths = []):
    return is_page(get_path(paths))

class AddActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name/action name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_action', name.split(' '))

  def is_visible(self, paths = []):
    return is_actions(get_path(paths))

class RemoveActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Remove Action: Feature name/action name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    if sublime.ok_cancel_dialog('Remove Action: %s?' % name, 'Remove'):
      run_script(get_path(paths), 'rm_action', name.split(' '))

  def is_visible(self, paths = []):
    return is_actions(get_path(paths))

class AddAsyncActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name/async action name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_async_action', name.split(' '))

  def is_visible(self, paths = []):
    return is_actions(get_path(paths))

class RemoveAsyncActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Remove Async Action: Feature name/async action name:", get_feature_name(get_path(paths)) + '/', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    if sublime.ok_cancel_dialog('Remove Async Action: %s?' % name, 'Remove'):
      run_script(get_path(paths), 'rm_async_action', name.split(' '))

  def is_visible(self, paths = []):
    return is_actions(get_path(paths))

class UnitTestCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    rekitRoot = get_rekit_root(paths[0])
    targetName = get_filename_without_ext(paths[0])
    featureName = None
    if is_feature_element(paths[0]):
      featureName = get_feature_name(paths[0])
      testPath = os.path.join(rekitRoot, 'test/app/features/%s/%s.test.js' % (featureName, targetName))
    else:
      testPath = os.path.join(rekitRoot, 'test/app/components/%s.test.js' % targetName)

    if os.path.exists(testPath):
      Window().open_file(testPath)
    else:
      if sublime.ok_cancel_dialog('The unit test file doesn\'t exist, create it? '):
        print('abc')
        # run_script(get_path(paths), 'rm_async_action', name.split(' '))


  def on_done(self, paths, relative_to_project, name):
    if sublime.ok_cancel_dialog('Remove Async Action: %s?' % name, 'Remove'):
      run_script(get_path(paths), 'rm_async_action', name.split(' '))

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_actions(p) or is_page(p) or is_component(p) or is_reducer(p)
