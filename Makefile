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

.PHONY: help sync dev-link dev-unlink remote-github remote-local show

##
### Usage assistance
##
help: ## display this Help Message
	@IFS=$$'\n'; for line in `grep -h -E '^[a-zA-Z_#-]+:?.*?## .*$$' $(MAKEFILE_LIST)`; do if [ "$${line:0:2}" = "##" ]; then \
	echo $$line | awk 'BEGIN {FS = "## "}; {printf "\n\033[33m%s\033[0m\n", $$2}'; else \
	echo $$line | sed -e 's/$${KIND_CLUSTER_NAME}/${KIND_CLUSTER_NAME}/' | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'; fi; \
	done; unset IFS;

##
### Environment
##
sync: ## Synchronise the python environment
	uv sync

##
### dunetrg source
##
dev-link: ## Develop against the local ../dunetrg checkout (editable)
	uv add --editable "$(PARENT)/$(LIB)" --extra all

dev-unlink: ## Go back to the pinned tag (TAG=...)
	uv add "$(LIB)[all] @ git+file://$(PARENT)/$(LIB)@$(TAG)"

remote-github: ## Point at GitHub over SSH (OWNER=..., TAG=...)
	uv add "$(LIB)[all] @ git+ssh://git@github.com/$(OWNER)/$(LIB).git@$(TAG)"

remote-local: ## Point back at the local repository
	uv add "$(LIB)[all] @ git+file://$(PARENT)/$(LIB)@$(TAG)"

show: ## Print the current [tool.uv.sources] entries
	@awk '/^\[tool.uv.sources\]/{f=1;next} /^\[/{f=0} f&&NF' pyproject.toml
