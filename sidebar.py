#!/usr/bin/python
import os
import sublime
import sublime_plugin
import logging
import functools
import re
import subprocess
import threading
import webbrowser
import codecs

LOCAL_PATH = ''
if not os.name == 'nt':
  LOCAL_PATH = ':/usr/local/bin:/usr/local/sbin:/usr/local/share/npm/bin:/usr/local/share/node/bin'

def Window():
  return sublime.active_window()

def main_thread(callback, *args, **kwargs):
  # sublime.set_timeout gets used to send things onto the main thread
  # most sublime.[something] calls need to be on the main thread
  sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

class CommandThread(threading.Thread):
  def __init__(self, command, on_done, working_dir=None, shell="", env={}):
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
      envPATH = os.environ['PATH'] + LOCAL_PATH
      s = sublime.load_settings("Rekit.sublime-settings")
      if s.get('node_dir') and envPATH.find(s.get('node_dir')) == -1:
        envPATH = envPATH + os.pathsep + s.get('node_dir')
      if s.get('npm_dir') and envPATH.find(s.get('npm_dir')) == -1:
        envPATH = envPATH + os.pathsep + s.get('npm_dir')
      p = subprocess.Popen(self.command, cwd=self.working_dir, env={'PATH': envPATH}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, startupinfo=si)
      for line in iter(p.stdout.readline, b''):
        line2 = line.decode().strip('\r\n')
        # only show output for mocha     
        if re.search(r'run_test\.js|build\.js', self.command[1]) is not None:
          show_rekit_output(line2)
      if self.on_done:
        self.on_done()

    except subprocess.CalledProcessError as e:
      # show_rekit_output(str(e))
      show_rekit_output('running node failed:')
      show_rekit_output(str(e))
      sublime.error_message(str(e))

    except OSError as e:
      if e.errno == 2:
        main_thread(sublime.error_message, "Node binary could not be found in PATH\nConsider using the node_dir and npm_dir settings for the Rekit plugin\n\nPATH is: %s" % os.environ['PATH'])
      else:
        show_rekit_output('running node failed:')
        show_rekit_output(str(e))
        raise e

    except Exception as e:
      show_rekit_output('running node failed:')
      show_rekit_output(str(e))

def run_command(command, callback=None, show_status=True, filter_empty_args=True, cwd=None, **kwargs):
  if filter_empty_args:
    command = [arg for arg in command if arg]
  
  # node_cmd = s.get('node_command')
  # npm_cmd =s.get('npm_command')
  # if command[0] == 'node' and node_cmd:
  #   command[0] = node_cmd

  # if command[0] == 'npm' and npm_cmd:
  #   command[0] = npm_cmd

  thread = CommandThread(command, callback, working_dir=cwd, **kwargs)
  thread.start()

def run_script(path, name, args = [], on_done=None):
  js_file = os.path.join(get_rekit_root(path), 'tools/cli', name + '.js').replace('\\', '/').replace('\\', '/')
  run_command(['node', js_file] + args, callback=on_done)

def is_rekit_root(path):
  if path is None:
    return False
  return os.path.exists(os.path.join(path, 'src/features').replace('\\', '/')) \
    and os.path.exists(os.path.join(path, 'tools/cli/templates/Page.js').replace('\\', '/'))

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
  return is_rekit_project(path) and re.search(r'src/features/\w+', path) is not None;

def is_components_folder(path):
  return is_rekit_project(path) and re.search(r'src/components/?$', path, re.I) is not None

def is_page(path):
  return False

def is_component(path):
  if not is_rekit_project(path):
    return False
  filename = os.path.basename(path)

  if re.search(r'src\/components|src\/features', path) is None:
    return False

  if re.search(r'^([A-Z]+[a-z0-9]*)+\.', filename) is None:
    return False

  if re.search(r'\.js$|\.less$|\.scss$|\.css$', filename) is None:
    return False

  path = re.sub(r'\.less$|\.scss$|\.css$', '.js', path)
  if not os.path.exists(path):
    return False

  text = codecs.open(path, 'r', 'utf8').read()
  if re.search('class ' + get_filename_without_ext(filename) + ' extends', text, re.MULTILINE) is None:
    return False

  if re.search('export default connect\(', text, re.MULTILINE) is not None:
    return False

  return True

def is_feature_component(path):
  return is_feature_element(path) and is_component(path)

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

  text = codecs.open(path, 'r', 'utf8').read()
  if re.search('class ' + get_filename_without_ext(filename) + ' extends', text, re.MULTILINE) is None:
    return False

  if re.search('export default connect\(', text, re.MULTILINE) is None:
    return False

  return True

def is_redux_folder(path):
  return is_rekit_project(path) and re.search(r'src/features/[^/]+/redux/?$', path, re.I) is not None

def is_reducer(path):
  return os.path.basename(path) == 'reducer.js' \
    and is_rekit_project(path) \
    and is_redux_folder(os.path.dirname(path))

def is_action(path):
  if re.search(r'src\/features\/[^\/]+\/redux', path) is None:
    return False

  actionsPath = os.path.join(os.path.dirname(path), 'actions.js')
  if not os.path.exists(actionsPath):
    return False

  text = codecs.open(actionsPath, 'r', 'utf8').read()
  if text.find("'./" + get_filename_without_ext(path) + "';") == -1:
    return False

  return True

def is_async_action(path):
  if re.search(r'src\/features\/[^\/]+\/redux', path) is None:
    return False

  actionsPath = os.path.join(os.path.dirname(path), 'actions.js')
  if not os.path.exists(actionsPath):
    return False

  actionName = get_filename_without_ext(path)
  text = codecs.open(path, 'r', 'utf8').read()
  # TODO: check constants to make it more precise
  return re.search('function ' + actionName + r'\(', text, re.I) is not None \
    and re.search('function dismiss' + actionName + r'Error\(', text, re.I) is not None

def is_test(path):
  if not is_rekit_project(path):
    return False
  return bool(re.search(r'\/test\/.*\.test\.js$', path))

def is_test_folder(path):
  if not is_rekit_project(path):
    return False
  return bool(re.search(r'\/test\/?$', path)) and os.path.isdir(path)

def is_app_test_folder(path):
  if not is_rekit_project(path):
    return False
  return bool(re.search(r'\/test/app\/?$', path)) and os.path.isdir(path)

def is_cli_test_folder(path):
  if not is_rekit_project(path):
    return False
  return bool(re.search(r'\/test/cli\/?$', path)) and os.path.isdir(path)

def is_sub_test_folder(path):
  if not is_rekit_project(path):
    return False
  return bool(re.search(r'\/test\/\w+', path)) and os.path.isdir(path)

def is_other():
  return True

def get_path(paths):
  return paths[0].replace('\\', '/')

class RekitAddFeatureCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Feature name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    run_script(get_path(paths), 'add_feature', [name])

  def is_visible(self, paths = []):
    return is_features_folder(get_path(paths))

class RekitRemoveFeatureCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    feature_name = get_feature_name(get_path(paths))
    if sublime.ok_cancel_dialog('Remove Feature: %s?' % feature_name, 'Remove'):
      run_script(get_path(paths), 'rm_feature', [feature_name])

  def is_visible(self, paths = []):
    return is_feature(get_path(paths))

class RekitAddComponentCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Component name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    args = [name]
    p = get_path(paths)
    if is_feature(p):
      featureName = get_feature_name(p)
      args = [featureName + '/' + name]
    run_script(p, 'add_component', args)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_feature(p) or is_components_folder(p)

class RekitRemoveComponentCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    feature_name = None
    component_name = get_filename_without_ext(get_path(paths))
    args = component_name
    if is_feature_component(p):
      feature_name = get_feature_name(p)
      args = '%s/%s' % (feature_name, component_name)

    if sublime.ok_cancel_dialog('Remove Component: %s?' % args, 'Remove'):
      Window().run_command('close')
      run_script(get_path(paths), 'rm_component', [args])
  def is_visible(self, paths = []):
    return is_component(get_path(paths))

class RekitAddPageCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Page name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    p = get_path(paths)
    featureName = get_feature_name(p)
    run_script(get_path(paths), 'add_page', (featureName + '/' + name).split(' '))

  def is_visible(self, paths = []):
    return is_feature(get_path(paths))

class RekitRemovePageCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    feature_name = get_feature_name(get_path(paths))
    page_name = get_filename_without_ext(get_path(paths))
    if sublime.ok_cancel_dialog('Remove Page: %s/%s?' % (feature_name, page_name), 'Remove'):
      Window().run_command('close')
      run_script(get_path(paths), 'rm_page', ['%s/%s' % (feature_name, page_name)])
  def is_visible(self, paths = []):
    return is_page(get_path(paths))

class RekitAddActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Action name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    p = get_path(paths)
    featureName = get_feature_name(p)
    run_script(get_path(paths), 'add_action', (featureName + '/' + name).split(' '))

  def is_visible(self, paths = []):
    return is_redux_folder(get_path(paths))

class RekitRemoveActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    featureName = get_feature_name(p)
    actionName = get_filename_without_ext(p)
    if sublime.ok_cancel_dialog('Remove Action: %s/%s?' % (featureName, actionName), 'Remove'):
      Window().run_command('close')
      run_script(p, 'rm_action', ['%s/%s' % (featureName, actionName)])

  def on_done(self, paths, relative_to_project, name):
    if sublime.ok_cancel_dialog('Remove Action: %s?' % name, 'Remove'):
      run_script(get_path(paths), 'rm_action', name.split(' '))

  def is_visible(self, paths = []):
    p = get_path(paths);
    return is_action(p) and not is_async_action(p)

class RekitAddAsyncActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    Window().show_input_panel("Async action name:", '', functools.partial(self.on_done, paths, False), None, None)

  def on_done(self, paths, relative_to_project, name):
    p = get_path(paths)
    featureName = get_feature_name(p)
    run_script(get_path(paths), 'add_async_action', (featureName + '/' + name).split(' '))

  def is_visible(self, paths = []):
    return is_redux_folder(get_path(paths))

class RekitRemoveAsyncActionCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    featureName = get_feature_name(p)
    actionName = get_filename_without_ext(p)
    if sublime.ok_cancel_dialog('Remove Async Action: %s/%s?' % (featureName, actionName), 'Remove'):
      Window().run_command('close')
      run_script(p, 'rm_async_action', ['%s/%s' % (featureName, actionName)])

  def is_visible(self, paths = []):
    return is_async_action(get_path(paths))

class RekitUnitTestCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    rekitRoot = get_rekit_root(p)
    targetName = get_filename_without_ext(p)
    featureName = None
    if is_reducer(p):
      featureName = get_feature_name(p)
      testPath = os.path.join(rekitRoot, 'test/app/features/%s/redux/reducer.test.js' % featureName)
      if not os.path.exists(testPath):
        if sublime.ok_cancel_dialog('The test file doesn\'t exist, create it? '):
          script = 'add_reducer_test'
          run_script(p, script, [featureName], on_done=functools.partial(self.on_test_created, testPath))
      else:
        Window().open_file(testPath)
    if is_action(p):
      featureName = get_feature_name(p)
      testPath = os.path.join(rekitRoot, 'test/app/features/%s/redux/%s.test.js' % (featureName, targetName))
      if not os.path.exists(testPath):
        if sublime.ok_cancel_dialog('The test file doesn\'t exist, create it? '):
          script = 'add_action_test'
          if is_async_action(p):
            script = 'add_async_action_test';
          run_script(p, script, [featureName + '/' + targetName], on_done=functools.partial(self.on_test_created, testPath))
      else:
        Window().open_file(testPath)

      return
    elif is_page(p):
      featureName = get_feature_name(p)
      testPath = os.path.join(rekitRoot, 'test/app/features/%s/%s.test.js' % (featureName, targetName))
      if not os.path.exists(testPath):
        if sublime.ok_cancel_dialog('The test file doesn\'t exist, create it? '):
          script = 'add_page_test'
          run_script(p, script, [featureName + '/' + targetName], on_done=functools.partial(self.on_test_created, testPath))
      else:
        Window().open_file(testPath)

    elif is_feature_component(p):
      featureName = get_feature_name(p)
      testPath = os.path.join(rekitRoot, 'test/app/features/%s/%s.test.js' % (featureName, targetName))
      if not os.path.exists(testPath):
        if sublime.ok_cancel_dialog('The test file doesn\'t exist, create it? '):
          script = 'add_component_test'
          run_script(p, script, [featureName + '/' + targetName], on_done=functools.partial(self.on_test_created, testPath))
      else:
        Window().open_file(testPath)
    elif is_component(p):
      testPath = os.path.join(rekitRoot, 'test/app/components/%s.test.js' % targetName)
      if not os.path.exists(testPath):
        if sublime.ok_cancel_dialog('The test file doesn\'t exist, create it? '):
          script = 'add_component_test'
          run_script(p, script, [targetName], on_done=functools.partial(self.on_test_created, testPath))
      else:
        Window().open_file(testPath)

  def on_test_created(self, testPath):
    Window().open_file(testPath)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_action(p) or is_page(p) or is_component(p) or is_reducer(p)


def get_test_output_panel():
  panel = Window().find_output_panel('rekit_output_panel')
  if panel is None:
    panel = Window().create_output_panel('rekit_output_panel')
    panel.set_read_only(True)
  return panel

class RekitOutputCommand(sublime_plugin.TextCommand):
  def run(self, edit, **args):
    self.view.set_read_only(False)
    if args.get('clear'):
      self.view.erase(edit, sublime.Region(0, self.view.size()))
    else:
      self.view.insert(edit, self.view.size(), args.get('text') + '\n')
    self.view.set_read_only(True)

def show_rekit_output(text):
  panel = get_test_output_panel()
  Window().run_command('show_panel', { 'panel': 'output.rekit_output_panel' })
  panel.run_command('rekit_output', {'text': text})

def show_rekit_output_panel():
  panel = get_test_output_panel()
  Window().run_command('show_panel', { 'panel': 'output.rekit_output_panel' })

def clear_rekit_output():
  panel = get_test_output_panel()
  Window().run_command('show_panel', { 'panel': 'output.rekit_output_panel' })
  panel.run_command('rekit_output', { 'clear': True })

class RekitRunTestCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    rekitRoot = get_rekit_root(paths[0])
    clear_rekit_output()
    show_rekit_output_panel()
    run_command([
      'node',
      './tools/run_test.js',
      p.replace(os.path.join(rekitRoot, 'test/'), '')
    ], cwd=rekitRoot)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_test(p)

class RekitRunTestsCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    rekitRoot = get_rekit_root(paths[0])
    clear_rekit_output()
    show_rekit_output_panel()
    run_command([
      'node',
      './tools/run_test.js',
      p.replace(os.path.join(rekitRoot, 'test/'), '')
    ], cwd=rekitRoot)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_sub_test_folder(p)
class RekitRunAllTestsCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    rekitRoot = get_rekit_root(paths[0])
    clear_rekit_output()
    show_rekit_output_panel()
    run_command([
      'node',
      './tools/run_test.js',
      'all'
    ], cwd=rekitRoot)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_test_folder(p)

class RekitTestCoverageCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    rekitRoot = get_rekit_root(p)
    reportType = ''
    if is_app_test_folder(p):
      reportType = 'app'
    elif is_cli_test_folder(p):
      reportType = 'cli'
    reportPath = os.path.join(rekitRoot, 'coverage', reportType, 'lcov-report/index.html')
    webbrowser.open('file://' + reportPath)

  def is_enabled(self, paths = []):
    if not self.is_visible(paths):
      return False
    p = get_path(paths)
    rekitRoot = get_rekit_root(p)
    reportType = ''
    if is_app_test_folder(p):
      reportType = 'app'
    elif is_cli_test_folder(p):
      reportType = 'cli'
    reportPath = os.path.join(rekitRoot, 'coverage', reportType, 'lcov-report/index.html')
    return os.path.exists(reportPath)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_test_folder(p) or is_app_test_folder(p) or is_cli_test_folder(p)

class RekitBuildCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    p = get_path(paths)
    rekitRoot = get_rekit_root(paths[0])
    clear_rekit_output()
    show_rekit_output_panel()
    run_command(['node', './tools/build.js'], cwd=rekitRoot)

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_rekit_root(p)

class RekitShowOutputCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    show_rekit_output_panel()

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_rekit_root(p)

class RekitClearOutputCommand(sublime_plugin.WindowCommand):
  def run(self, paths = []):
    rekitRoot = get_rekit_root(paths[0])
    clear_rekit_output()

  def is_visible(self, paths = []):
    p = get_path(paths)
    return is_rekit_root(p)
