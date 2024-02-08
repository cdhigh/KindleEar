#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#To generate builtin_recipes.zip and builtin_recipes.xml, execute this script

import os, sys, re, io, glob, zipfile, tempfile, builtins, shutil
from xml.sax.saxutils import quoteattr

builtins.__dict__['_'] = lambda x: x
thisDir = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(thisDir, '..', 'application', 'lib')))

from calibre import force_unicode
from calibre.web.feeds.recipes import compile_recipe

recipesDir = os.path.abspath(os.path.join(thisDir, '..', 'application', 'recipes'))

#old_recipes_dir: recipes extracted from builtin_recipes.zip
def iterate_recipe_files(recipes_dir, old_recipes_dir):
    exclude = ['craigslist.recipe', 'toronto_sun.recipe']
    added = set()
    dirs = [recipes_dir, old_recipes_dir] if old_recipes_dir else [recipes_dir]
    for dir_ in dirs:
        for f in os.listdir(dir_):
            if not f.endswith('.recipe') or f in exclude:
                continue

            f = os.path.join(dir_, f)
            recipe_id = os.path.splitext(os.path.relpath(f, dir_).replace('\\', '/'))[0]
            if recipe_id not in added:
                added.add(recipe_id)
                yield recipe_id, f

def normalize_language(x: str) -> str:
    lang, sep, country = x.replace('-', '_').partition('_')
    if sep == '_':
        x = f'{lang.lower()}{sep}{country.upper()}'
    else:
        x = lang.lower()
    return x

def serialize_recipe(urn, recipe_class):
    def attr(n, d, normalize=lambda x: x):
        ans = getattr(recipe_class, n, d)
        if isinstance(ans, bytes):
            ans = ans.decode('utf-8', 'replace')
        return quoteattr(normalize(ans))

    default_author = 'You' if urn.startswith('custom:') else 'Unknown'
    ns = getattr(recipe_class, 'needs_subscription', False)
    if not ns:
        ns = 'no'
    if ns is True:
        ns = 'yes'
    return ('  <recipe id={id} title={title} author={author} language={language}'
            ' needs_subscription={needs_subscription} description={description}/>').format(**{
        'id'                 : quoteattr(str(urn)),
        'title'              : attr('title', 'Unknown'),
        'author'             : attr('__author__', default_author),
        'language'           : attr('language', 'und', normalize_language),
        'needs_subscription' : quoteattr(ns),
        'description'        : attr('description', '')
        })

def serialize_collection(mapping_of_recipe_classes):
    collection = []
    for urn in sorted(mapping_of_recipe_classes.keys(),
            key=lambda key: force_unicode(getattr(mapping_of_recipe_classes[key], 'title', 'zzz'), 'utf-8')):
        try:
            recipe = serialize_recipe(urn, mapping_of_recipe_classes[urn])
        except:
            import traceback
            traceback.print_exc()
            continue

        collection.append(recipe)

    items = '\n'.join(collection)

    return f'''<?xml version='1.0' encoding='utf-8'?>
<recipe_collection xmlns="http://calibre-ebook.com/recipe_collection" count="{len(collection)}">
{items}
</recipe_collection>'''.encode()

#old_recipes_dir: recipes extracted from builtin_recipes.zip
def serialize_builtin_recipes(recipes_dir, old_recipes_dir):
    recipe_mapping = {}
    skipped = 0
    for recipe_id, f in iterate_recipe_files(recipes_dir, old_recipes_dir):
        urn = f'builtin:{recipe_id}'
        with open(f, 'rb') as stream:
            try:
                recipe_class = compile_recipe(stream.read())
            except Exception as e:
                print(f'Failed to compile: {f}, skipped. Error:\n{e}')
                skipped += 1
                continue
        if recipe_class is not None:
            recipe_mapping[urn] = recipe_class

    return len(recipe_mapping), skipped, serialize_collection(recipe_mapping)

#determinate by modified time
def newer(targets, sources):
    if hasattr(targets, 'rjust'):
        targets = [targets]
    if hasattr(sources, 'rjust'):
        sources = [sources]
    for f in targets:
        if not os.path.exists(f):
            return True
    ttimes = map(lambda x: os.stat(x).st_mtime, targets)
    oldest_target = min(ttimes)
    try:
        stimes = map(lambda x: os.stat(x).st_mtime, sources)
        newest_source = max(stimes)
    except:
        newest_source = oldest_target + 1

    return newest_source > oldest_target

def archive_builtin_recipes(recipes_dir):
    xml_name = os.path.join(recipes_dir, 'builtin_recipes.xml')
    zip_name = os.path.join(recipes_dir, 'builtin_recipes.zip')
    try:
        files = next(iterate_recipe_files(recipes_dir, ''))
    except StopIteration:
        files = []

    old_recipes_dir = ''
    if files and os.path.exists(zip_name):
        print('\tFound builtin_recipes.zip, extracting')
        old_recipes_dir = tempfile.mkdtemp(prefix='builtin_recipes_')
        with zipfile.ZipFile(zip_name, 'r') as zfile:
            zfile.extractall(old_recipes_dir)
        
    files = [x[1] for x in iterate_recipe_files(recipes_dir, old_recipes_dir)]

    created = []
    if newer(xml_name, files):
        print('\tCreating builtin_recipes.xml')
        num, skipped, xml = serialize_builtin_recipes(recipes_dir, old_recipes_dir)
        if num:
            with open(xml_name, 'wb') as f:
                f.write(xml)
            print(f'\n\tbuiltin_recipes.xml contains {num} recipes, skipping {skipped}.')
            created.append('builtin_recipes.xml')
        else:
            print(f'\tCannot found any standalone recipe file in : {recipes_dir}')
            return
    else:
        print('\tbuiltin_recipes.xml is up-to-date and does not need to be regenerated.')

    #pngAdded = set()
    #for d in [recipes_dir, old_recipes_dir]:
    #    for f in glob.glob(os.path.join(d, 'icons', '*.png')):
    #        bname = os.path.basename(f)
    #        if bname not in pngAdded:
    #            pngAdded.add(bname)
    #            files.append(f)
    
    if newer(zip_name, files):
        print('\tCreating builtin_recipes.zip')
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_STORED) as zf:
            for n in sorted(files, key=os.path.basename):
                with open(n, 'rb') as f:
                    zf.writestr(os.path.basename(n), f.read())
        print(f'\tbuiltin_recipes.zip created')
        created.append('builtin_recipes.zip')
    else:
        print('\tbuiltin_recipes.zip is up-to-date and does not need to be regenerated.')

    if old_recipes_dir:
        shutil.rmtree(old_recipes_dir)

    return created

def main():
    print('\n---------------------------------------------------')
    print('The script will create the "builtin_recipes.xml" and "builtin_recipes.zip"\nfrom the recipes directory.')
    print('---------------------------------------------------')
    confirm = input('Press Y to continue, or N to exit : ')
    if confirm.strip().lower() == 'y':
        created = archive_builtin_recipes(recipesDir)

if __name__ == '__main__':
    sys.exit(main())
