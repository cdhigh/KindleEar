#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""Trim builtin_recipes.zip/builtin_recipes.xml for KindleEar
Due to being a utility script, all file read/write exceptions are ignored.
Usage: python trim_recipes.py en zh es
"""
import re, os, sys, zipfile
import xml.etree.ElementTree as ET

def main():
    if len(sys.argv) <= 1:
        print('Trim builtin_recipes.zip/builtin_recipes.xml')
        print('Usage: python trim_recipes.py en zh es')
        print('')
        return

    langList = []
    for item in ','.join(sys.argv[1:]).replace(';', ',').replace(' ', '').split(','):
        langList.append(item.replace('_', '-').split('-')[0].lower())

    thisDir = os.path.abspath(os.path.dirname(__file__))
    xmlFile = os.path.normpath(os.path.join(thisDir, '../application/recipes/builtin_recipes.xml'))
    reciZipFile = os.path.normpath(os.path.join(thisDir, '../application/recipes/builtin_recipes.zip'))
    if not os.path.exists(xmlFile) or not os.path.exists(reciZipFile):
        print('Cannot found builtin_recipes.xml/builtin_recipes.zip')
        return

    print(f'Triming recipes files using language list: {langList}')
    size0 = os.path.getsize(xmlFile)
    recipeFiles = trimXml(xmlFile, langList)
    size1 = os.path.getsize(xmlFile)
    if not recipeFiles: #we should continue, somebody might want to remove all of them.
        print('All recipes were removed! Please check your language list.')

    
    print(f'The builtin_recipes.xml file was reduced from {filesizeformat(size0)} to {filesizeformat(size1)}.')

    size0 = os.path.getsize(reciZipFile)
    trimZip(reciZipFile, recipeFiles)
    size1 = os.path.getsize(reciZipFile)
    print(f'The builtin_recipes.zip file was reduced from {filesizeformat(size0)} to {filesizeformat(size1)}.')

#Trim xml file using language list, return a list of recipe file
def trimXml(xmlFile: str, langList: list):
    namespace = 'http://calibre-ebook.com/recipe_collection'
    ET.register_namespace('', namespace)
    tree = ET.parse(xmlFile)
    root = tree.getroot()
    recipeFiles = []
    toRemove = []
    for recipe in root.findall(f'{{{namespace}}}recipe'):
        id_ = recipe.get('id', '')
        language = recipe.get('language', '').replace('_', '-').split('-')[0].lower()
        if id_.startswith('builtin:') and language in langList:
            recipeFiles.append(f'{id_[8:]}.recipe')
        else:
            toRemove.append(recipe)
    for recipe in toRemove:
        root.remove(recipe)

    root.set('count', str(len(root.findall(f'{{{namespace}}}recipe'))))
    tree.write(xmlFile, encoding='utf-8', xml_declaration=True)
    return recipeFiles


#Trim recipe zip file using recipe file list
def trimZip(reciZipFile: str, recipeFiles: list):
    tmpFile = reciZipFile + '.zip'
    zin = zipfile.ZipFile(reciZipFile, 'r')
    zout = zipfile.ZipFile(tmpFile, 'w')
    for item in [e for e in zin.infolist() if e.filename in recipeFiles]:
        zout.writestr(item, zin.read(item.filename))
    zout.close()
    zin.close()
    os.remove(reciZipFile)
    os.rename(tmpFile, reciZipFile)

def filesizeformat(value, binary=False, suffix='B'):
    value = abs(float(value))
    if binary:
        base = 1024
        prefixes = ('', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi')
    else:
        base = 1000
        prefixes = ('', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')

    for unit in prefixes:
        if value < base:
            return f"{value:3.1f} {unit}{suffix}" if unit else f"{int(value)} {suffix}"
        value /= base
    return f"{value:.1f} {unit}{suffix}" #type:ignore

if __name__ == '__main__':
    main()