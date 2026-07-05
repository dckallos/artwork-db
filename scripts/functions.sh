# Source this file from a shell startup file to install project helper commands.

function tree-gitignore {
  command tree -a --gitignore "$@"
}
