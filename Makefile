# 星海仪表盘常用命令
#
# 需要 GNU Make 与 Python；文件操作均通过 Python 完成，
# 因此在 PowerShell / cmd / Git Bash 下都可直接运行。
#   winget install ezwinports.make
#   choco install make
#
# 用法：make help

PYTHON   ?= python
INPUT    ?= data/m0-slot.json

SHELL_OUT := dist/starsea_dashboard.html
DATA_OUT  := dist/starsea_dashboard_data.html
PAGES     := docs/index.html

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
	$(PYTHON) -c "import shutil; shutil.copyfile('$(SHELL_OUT)', '$(PAGES)')"
	@echo Updated $(PAGES) - shell

pages-data: build-data
	$(PYTHON) -c "import shutil; shutil.copyfile('$(DATA_OUT)', '$(PAGES)')"
	@echo Updated $(PAGES) - data

publish: pages-shell
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'add', '$(PAGES)'], check=True)"
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'commit', '-m', 'Update GitHub Pages (empty shell)'])"
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'push', 'origin', 'main'], check=True)"

publish-data: pages-data
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'add', '$(PAGES)'], check=True)"
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'commit', '-m', 'Update GitHub Pages (data)'])"
	$(PYTHON) -c "import subprocess; subprocess.run(['git', 'push', 'origin', 'main'], check=True)"

parser:
	$(PYTHON) src/starsea_parser.py summary

list:
	$(PYTHON) src/starsea_parser.py list --limit 20

serve:
	@echo "http://localhost:8000/"
	cd docs && $(PYTHON) -m http.server 8000

clean:
	$(PYTHON) -c "import pathlib, shutil; [p.unlink() for p in pathlib.Path('dist').glob('*.html')]; pathlib.Path('dist/cosmic_starsea.json').unlink(missing_ok=True); shutil.rmtree('src/__pycache__', ignore_errors=True)"
