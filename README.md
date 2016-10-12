## Sublime plugin

Sublime text is a widely used code editor for JavaScript developers. [Rekit sublime plugin](https://github.com/supnate/rekit-plugin) is created for it to support common Rekit tasks.

The plugin will auto detect Rekit projects and provide sidebar menus for the projects so that you can easily do common Rekit tasks like creating features, running tests etc.

From the Rekit demo video you can see how to use it:

[<img src="/youtube.png" width="400" alt="Rekit Demo"/>](https://youtu.be/9lqWoQjy-JY "Rekit Demo")

For Chinese, visit the demo on Youku:

[<img src="/youku.png" width="400" alt="Rekit Demo"/>](http://v.youku.com/v_show/id_XMTcyNTQxNzgwNA==.html "Rekit Demo")

Here is a quick look for the plugin:

<img src="/menus.png" width="500" alt="Rekit plugin"/>

## Easy installation
You can install this plugin through the Package Control.

Press <kbd>Cmd</kbd>/<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> to open the command palette.
Type “install package” and press <kbd>Enter</kbd>. Then search for “Rekit”

## Manual installation
Download the [latest release](https://github.com/supnate/rekit-plugin), extract and rename the directory to “Rekit”.
Move the directory inside your sublime Packages directory. (Preferences > Browse packages…)

## node/npm configuration
By default, Rekit plugin will auto detect `node` and `npm` commands from system environment variables. But if you use a node version manager like [nvm](https://github.com/creationix/nvm), you may need to configure it manually.

1. Open your sublime Packages directory (Preferences > Browse packages…)
2. Open Rekit directory
3. Open Rekit.sublime-settings file

By default the content is:
```javascript
{
  "node_dir": false,
  "npm_dir": false,
}
```
You need to config the container dir for node and npm separately(though they are usually the same), for example:
```javascript
{
  "node_dir": "/usr/local/bin",
  "npm_dir": "/usr/local/bin",
}
```

