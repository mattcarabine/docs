import yaml
import os
import re
from pathlib import Path
import shutil
import time
import traceback
from utils import *
from http_docublocks import *
from inline_docublocks import *
import argparse
from globals import *


frontMatterCapture = r"(?<=---\n)(.*?)(?=---)"
widgetRegex = r"{% .* %}[\n]+.*[\n]+{% .* %}"

infos = {"": {}}
currentWeight = 0


def structure_migration_new(label, document, manual):
	if document is None:
		directoryTree = open(f"{OLD_TOOLCHAIN}/_data/3.10-{manual}.yml")
		document = yaml.full_load(directoryTree)

		if manual != "manual":
			create_index("core-topics", {"text": manual.upper(), "href": "index.html"}, manual+"/")
			document = document[1:]

	extendedSection = ''
	if manual != "manual":
		extendedSection = manual +"/"

	for item in document:
		if "subtitle" in item:
			label = create_chapter(item, manual)
			continue

		if "divider" in item:
			continue
		if "Release Notes" in item["text"]:
			label = "Release Notes"

		if "Appendix" in item["text"]:
			label = "Appendix"

		if "children" in item:
			label = create_index(label, item, extendedSection)
			
			structure_migration_new(label, item["children"], extendedSection)
			labelSplit = label.split("/")
			label = "/".join(labelSplit[0:len(labelSplit)-1])
			continue
		else:
			label = create_files_new(label, item, extendedSection)


def create_chapter(item, manual):
	label = item["subtitle"].lower().replace(" ", "-")

	if manual != "manual":
		label = f"core-topics/{manual}/{label}"

	filepath = f'{NEW_TOOLCHAIN}/content/{label}/_index.md'
	Path(f'{NEW_TOOLCHAIN}/content/{label}').mkdir(parents=True, exist_ok=True)

	labelPage = Page()
	labelPage.frontMatter.title = item["subtitle"]
	labelPage.frontMatter.menuTitle = item["subtitle"]
	labelPage.frontMatter.weight = get_weight(currentWeight)
	labelPage.frontMatter.fileID = "fileID"
	infos[filepath] = {"title": item["subtitle"], "weight": get_weight(currentWeight)}

	file = open(filepath, "w")
	file.write(labelPage.toString())
	file.close()
	return label


def create_index(label, item, extendedSection):
	oldFileName = item["href"].replace(".html", ".md")
	folderName = item["text"].lower().replace(" ", "-").replace("/", "")
	label = label + "/" + folderName

	Path(f'{NEW_TOOLCHAIN}/content/{label}').mkdir(parents=True, exist_ok=True)

	indexPath = f'{NEW_TOOLCHAIN}/content/{label}/_index.md'
	oldFilePath = f'{OLD_TOOLCHAIN}/3.10/{extendedSection}{oldFileName}'
	shutil.copyfile(oldFilePath, indexPath)
	infos[indexPath] = {
		"title": f'\'{item["text"]}\'' if '@' in item["text"] else item["text"],
		"weight": get_weight(currentWeight),
		"fileID": oldFileName.replace(".md", "")
		}
	return label

def create_files_new(label, item, extendedSection):
	oldFileName = item["href"].replace(".html", ".md")
	oldFilePath = f'{OLD_TOOLCHAIN}/3.10/{extendedSection}{oldFileName}'.replace("//", "/")
	filePath = f'{NEW_TOOLCHAIN}/content/{label}/{oldFileName}'

	try:
		shutil.copyfile(oldFilePath, filePath)
	except FileNotFoundError:
		print(f"WARNING! FILE NOT FOUND IN OLD TOOLCHAIN {oldFilePath}")
		
	infos[filePath]  = {
		"title": f'\'{item["text"]}\'' if '@' in item["text"] else item["text"],
		"weight": get_weight(currentWeight),
		"fileID": oldFileName.replace(".md", "")
		}
	return label



# File processing jekyll-hugo migration phase
def processFiles():
	print(f"----- STARTING CONTENT MIGRATION")
	#print(menu)
	for root, dirs, files in os.walk(f"{NEW_TOOLCHAIN}/content", topdown=True):
		for file in files:
			processFile(f"{root}/{file}")
	print("------ CONTENT MIGRATION END")

def processFile(filepath):
	#print(f"Migrating {filepath} content")
	try:
		file = open(filepath, "r")
		buffer = file.read()
		file.close()
	except Exception as ex:
		print(traceback.format_exc())
		raise ex

	page = Page()

	#Front Matter
	if filepath in infos:
		page.frontMatter.menuTitle = infos[filepath]["title"]
		page.frontMatter.weight = infos[filepath]["weight"] if "weight" in infos[filepath] else 0
	_processFrontMatter(page, buffer)
	fileID = filepath.split("/")
	page.frontMatter.fileID = fileID[len(fileID)-1].replace(".md", "")
	if page.frontMatter.fileID == "_index":
		page.frontMatter.fileID = fileID[len(fileID)-2]
	if "fileID" in infos[filepath]:
		page.frontMatter.fileID = infos[filepath]["fileID"]


	buffer = re.sub(r"-{3}\n[\w\s:/#,()?’'\@&\[\]\*.>-]+\n-{3}", '', buffer)

	#Internal content
	_processChapters(page, buffer)

	file = open(filepath, "w")
	file.write(page.toString())
	file.close()

	return

def _processFrontMatter(page, buffer):
	frontMatterRegex = re.search(frontMatterCapture, buffer, re.MULTILINE | re.DOTALL)
	if not frontMatterRegex:
		return		# TODO

	frontMatter = frontMatterRegex.group(0)

	fmTitleRegex = re.search(r"(?<=title: ).*", frontMatter)
	if fmTitleRegex:
		page.frontMatter.title = fmTitleRegex.group(0)

	paragraphTitleRegex = re.search(r"(?<=---\n)(# .*)|(.*\n(?=={4,}))", buffer)
	if paragraphTitleRegex:
		page.frontMatter.title = paragraphTitleRegex.group(0).replace('#', '').replace(':', '')
		page.frontMatter.title = re.sub(r"{{ .* }}", '', page.frontMatter.title)
	
	set_page_description(page, buffer, frontMatter)

	return page

def _processChapters(page, paragraph):
	if paragraph is None or paragraph == '':
		return

	paragraph = re.sub("{+\s?page.description\s?}+", '', paragraph)
	paragraph = paragraph.replace("{:target=\"_blank\"}", "")
	test = re.search(r"#+ .*|(.*\n={4,})", paragraph)
	if test:
		paragraph = paragraph.replace(test.group(0), '', 1)

	paragraph = re.sub(r"(?<=\n\n)[\w\s\W]+{:class=\"lead\"}", '', paragraph)

	paragraph = migrate_headers(paragraph)
	paragraph = migrate_hrefs(paragraph)
	paragraph = migrate_hints(paragraph)
	paragraph = migrateHTTPDocuBlocks(paragraph)
	paragraph = migrateInlineDocuBlocks(paragraph)
	page.content = paragraph
	return


def migrate_media():
	print("----- MIGRATING MEDIA")
	for root, dirs, files in os.walk(f"{OLD_TOOLCHAIN}/3.10/images", topdown=True):
		for file in files:
			print(f"migrating {file}")
			shutil.copyfile(f"{root}/{file}", f"{NEW_TOOLCHAIN}/site/assets/images/{file}")

	for root, dirs, files in os.walk(f"{OLD_TOOLCHAIN}/3.10/oasis/images", topdown=True):
		for file in files:
			print(f"migrating {file}")
			shutil.copyfile(f"{root}/{file}", f"{NEW_TOOLCHAIN}/site/assets/images/{file}")
	print("----- END MEDIA MIGRATION")

class Page():
	def __init__(self):
		self.frontMatter = FrontMatter()
		self.content = ""

	def toString(self):
		res = self.frontMatter.toString()
		res = f"{res}\n{self.content}"
		return res

class FrontMatter():
	def __init__(self):
		self.title = ""
		self.layout = "default"
		self.fileID = ""
		self.description = ""
		self.menuTitle = ""
		self.weight = 0

	def toString(self):
		return f"---\nfileID: {self.fileID}\ntitle: {self.title}\nmenuTitle: {self.menuTitle}\nweight: {self.weight}\ndescription: {self.description}\nlayout: default\n---\n"

def get_weight(weight):
	global currentWeight
	currentWeight += 5
	return currentWeight

if __name__ == "__main__":
	print("Starting migration")
	try:
		structure_migration_new('', None, "manual")
		structure_migration_new('core-topics/http', None, "http")
		structure_migration_new('core-topics/oasis', None, "oasis")
		structure_migration_new('core-topics/aql', None, "aql")
		structure_migration_new('core-topics/drivers', None, "drivers")
		initBlocksFileLocations()
		processFiles()
		write_components_to_file()
		#migrate_media()
	except Exception as ex:
		print(traceback.format_exc())