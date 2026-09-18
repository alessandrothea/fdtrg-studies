# Where dunetrg comes from.
#
# Default (committed state): the dunetrg repository, pinned to a tag — see
# [tool.uv.sources] in pyproject.toml. A fresh clone builds on its own, and
# uv.lock pins the commit. The [all] extra pulls the emu and analysis stacks.
#
#   make sync                      install from the pinned tag
#   make dev-link                  develop against ../dunetrg
#   make dev-unlink                back to the pinned tag
#   make remote-github OWNER=you   after pushing: point at GitHub (SSH)
#   make remote-local              point back at the local repository
#   make show                      print the current source
#
# dev-link edits pyproject.toml and uv.lock, so it shows up in git status —
# don't commit it by accident. For a one-off run that changes no files:
#
#   uv run --with-editable ../dunetrg <command>

OWNER ?= alessandrothea
TAG   ?= v0.1.0
LIB   ?= dunetrg
PARENT := $(abspath $(CURDIR)/..)

.PHONY: sync dev-link dev-unlink remote-github remote-local show

sync:
	uv sync

dev-link:
	uv add --editable "$(PARENT)/$(LIB)" --extra all

dev-unlink:
	uv add "$(LIB)[all] @ git+file://$(PARENT)/$(LIB)@$(TAG)"

remote-github:
	uv add "$(LIB)[all] @ git+ssh://git@github.com/$(OWNER)/$(LIB).git@$(TAG)"

remote-local:
	uv add "$(LIB)[all] @ git+file://$(PARENT)/$(LIB)@$(TAG)"

show:
	@awk '/^\[tool.uv.sources\]/{f=1;next} /^\[/{f=0} f&&NF' pyproject.toml
