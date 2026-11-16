# 星海仪表盘常用命令
#
# 需要 GNU Make；Windows 可用 Git Bash 环境，或：
#   winget install ezwinports.make
#   choco install make
#
# 用法：make help

PYTHON   ?= python
INPUT    ?= data/m0-slot.json

SHELL_OUT := dist/starsea_dashboard.html
DATA_OUT  := dist/starsea_dashboard_data.html
PAGES     := docs/index.html

ifeq ($(OS),Windows_NT)
SHELL := bash
endif

.DEFAULT_GOAL := help
.PHONY: help build build-shell build-data pages pages-shell pages-data publish publish-data parser list serve clean

help:
	@echo "星海仪表盘"
	@echo ""
	@echo "  make build         构建空壳 + 数据版"
	@echo "  make build-shell   构建空壳  -> $(SHELL_OUT)"
	@echo "  make build-data    构建数据版 -> $(DATA_OUT)"
	@echo "  make pages         用空壳更新 $(PAGES)"
	@echo "  make pages-data    用数据版更新 $(PAGES)"
	@echo "  make publish       空壳更新并 push（GitHub Pages）"
	@echo "  make publish-data  数据版更新并 push（GitHub Pages）"
	@echo "  make parser        查看存档 summary"
	@echo "  make list          列出前 20 个档案"
	@echo "  make serve         本地预览 $(PAGES)（http://localhost:8000）"
	@echo "  make clean         清理构建产物"
	@echo ""
	@echo "  变量：INPUT=$(INPUT)  PYTHON=$(PYTHON)"

build: build-shell build-data

build-shell:
	$(PYTHON) src/build_starsea_dashboard.py

build-data:
	$(PYTHON) src/build_starsea_dashboard.py -i $(INPUT)

pages: pages-shell

pages-shell: build-shell
	cp $(SHELL_OUT) $(PAGES)
	@echo "已更新 $(PAGES)（空壳）"

pages-data: build-data
	cp $(DATA_OUT) $(PAGES)
	@echo "已更新 $(PAGES)（数据版）"

publish: pages-shell
	git add $(PAGES)
	git commit -m "Update GitHub Pages (empty shell)" || true
	git push origin main

publish-data: pages-data
	git add $(PAGES)
	git commit -m "Update GitHub Pages (data)" || true
	git push origin main

parser:
	$(PYTHON) src/starsea_parser.py summary

list:
	$(PYTHON) src/starsea_parser.py list --limit 20

serve:
	@echo "http://localhost:8000/"
	cd docs && $(PYTHON) -m http.server 8000

clean:
	rm -f dist/*.html dist/cosmic_starsea.json
	rm -rf src/__pycache__
