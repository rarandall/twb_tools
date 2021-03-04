import os
from flask import Flask, render_template, request, session, Response, send_from_directory, current_app
import uuid
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET
from google_trans_new import google_translator
#from googletrans import Translator
import pandas as pd
from six.moves import urllib
import re
import time

app = Flask(__name__)
app.secret_key = 'AoAv38dAf3vE392jdjsvRv765f?RT'

ALLOWED_EXTENSIONS = {'twb'}
UPLOAD_FOLDER = '/home/rarandall/calc_extractor/upload/'
OUTPUT_FOLDER = '/home/rarandall/calc_extractor/output/'

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_PATH'] = 50000

now = time.time()

def allowed_file(filename):
  return '.' in filename and \
         filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload", methods=['GET', 'POST'])
def index():
    session['uid'] = uuid.uuid4()
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename_h = str(session['uid'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_h))
            # message = filename + " uploaded"
            df = get_calc(UPLOAD_FOLDER+filename_h)
            p_df = pd.DataFrame(df, columns=['Datasource', 'Type', 'Name', 'Remote_Name', 'Formula', 'Comment', 'Fields'])
            fields = get_fields(p_df)
            paths = get_paths(p_df)
            return render_template('output.html', filename=df, fileid=filename_h, fields=fields, paths=paths)
        else:
            error = "Not a valid twb file"
            return render_template('upload.html', error=error)
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        if os.stat(os.path.join(app.config['UPLOAD_FOLDER'], file)).st_ctime < now - 86400:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))
    return render_template('upload.html')

@app.route("/csv", methods=['POST'])
def csv():
    if request.method == 'POST':
        f = request.form.get("fileid")
        lol = get_calc(UPLOAD_FOLDER+f)
        df = pd.DataFrame(lol, columns=['Datasource', 'Type', 'Name', 'Remote_Name', 'Formula', 'Comment', 'Fields'])
        csv_data = df.to_csv()
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition":
                         "attachment; filename=export.csv"})

    else:
        error = "First, upload a twb file"
        return render_template('upload.html', error=error)

@app.route("/translate", methods=['GET', 'POST'])
def translate():
    session['uid'] = uuid.uuid4()
    if request.method == 'POST':
        file = request.files['file']
        dest = request.form['dest']
        src = request.form['src']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename_h = str(session['uid'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_h))
            translate_twb(UPLOAD_FOLDER + filename_h,src,dest,filename_h)
            output = os.path.join(current_app.root_path, app.config['OUTPUT_FOLDER'])
            filename_path = filename_h + '.twb'
            attachment_name = filename.replace('.twb','')+'_'+dest+'.twb'
            for file in os.listdir(app.config['UPLOAD_FOLDER']):
                if os.stat(os.path.join(app.config['UPLOAD_FOLDER'], file)).st_mtime < now - 86400:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))
            for file in os.listdir(output):
                if os.stat(os.path.join(output, file)).st_mtime < now - 86400:
                    os.remove(os.path.join(output, file))
            return send_from_directory(directory=output, filename=filename_path, as_attachment=True,
                                       attachment_filename=attachment_name)
        else:
            error = 'Not a valid twb file'
            return render_template('translate.html', error=error)
    else:
        return render_template('translate.html')

@app.route("/disclaimer", methods =['GET'])
def disclaimer():
    if request.method == 'GET':
        return render_template('disclaimer.html')

def get_fields(df):
    # input a dataframe
    # output a list of key values [{ key:1, text: field_1 }, { key:2, text: field_2 }]
    fields = []
    # first, remove all parameters from df
    df = df[~df.Remote_Name.str.startswith('[Parameter ')]
    # get all values from Name column
    for i in range(len(df)):
        fields.append(df.iloc[i]['Name'])
    # get fields referenced in formula (ie. any string with [ ] or [Parameter].[ ] )
    for i in range(len(df)):
        s = df.iloc[i]['Formula']
        s = s.replace('[Parameters].[','[Parameter: ')
        a = re.findall('\[.*?\]',s)
        fields = fields + a
    fields.sort()
    fields = list(dict.fromkeys(fields))
    field_kvs = []
    for i, n in enumerate(fields):
        kv = {}
        kv['key'] = i
        kv['text'] = n
        field_kvs.append(kv)
    return field_kvs

def get_paths(df):
    # for each row in df, get the fields in formula as a list
    # create a list of key value pairs
    # for each field in formula, from=field in formula_key, to=name_key text='' { from: 1, to: 2, text: "" }
    key_dict = get_fields(df)
    paths_kvs = []
    for i in range(len(df)):
        s = df.iloc[i]['Formula']
        s = s.replace('[Parameters].[','[Parameter: ')
        formula_fields = re.findall('\[.*?\]', s)
        for field in formula_fields:
            kv = {}
            for dict in key_dict:
                if dict.get('text') == field.replace('[Parameters].[','[Parameter: '):
                    kv['from'] = dict.get('key')
                if dict.get('text') == df.iloc[i]['Name']:
                    kv['to'] = dict.get('key')
                    kv['text'] = 'o'
            if len(kv) == 3 and kv not in paths_kvs:
                paths_kvs.append(kv)
    return paths_kvs

def get_calc(file):
    # parse the twb file
    tree = ET.parse(file)
    root = tree.getroot()

    # create a dictionary of name and tableau generated name

    calcDict = {}
    notcalcSet = set()

    for child in root.iter('column'):
        if child.find('calculation') is not None:
            if child.get('caption') is not None:
                calcDict[child.attrib['name']] = '[' + child.get('caption') + ']'
        else:
            if child.get('name') is not None:
                notcalcSet.add(child.get('name'))

    # list of calc's name, tableau generated name, and calculation/formula
    calcList = []
    paramList = []

    for ds in root.iter("datasource"):
        if ds.get("name") == "Parameters":
            datasource = "Parameter"
        else:
            datasource = ds.get("caption")
        for item in ds.iter('column'):
            if item.find("calculation") is not None:
                if item.get('caption') is not None:
                    calc_type = item.get('role')
                    calc_caption = '[' + item.get('caption') + ']'
                    if datasource == "Parameter":
                        paramList.append(item.attrib['name'])
                        calc_name = item.attrib['name']
                    else:
                        calc_name = item.attrib['name']
                    calc_raw_formula = item.find("calculation").attrib["formula"]
                    calc_comment = ''
                    calc_formula = ''
                    for line in calc_raw_formula.splitlines():
                        if line.startswith('//'):
                            calc_comment = calc_comment + line + ' '
                            calc_comment = calc_comment.replace('//','')
                        else:
                            calc_formula = calc_formula + line + ' '
                    for name, caption in calcDict.items():
                        calc_formula = calc_formula.replace(name, caption)

                    # get fields from formula and add to list
                    fieldList = []
                    # remove parameter tags
                    formula_no_ptag = calc_formula.replace('[Parameters].','')
                    # search for fields
                    formula_fields = re.findall('\[(.*?)\]', formula_no_ptag)
                    # remove non-field values
                    for field in formula_fields:
                        field = "["+field+"]"
                        if field in calcDict.values():
                            fieldList.append(field)
                        elif field in notcalcSet:
                            fieldList.append(field)
                    fieldList = set(fieldList)
                    fieldList = ', '.join(fieldList)
                    calc_row = (datasource, calc_type, calc_caption, calc_name, calc_formula, calc_comment, fieldList)
                    if datasource != "Parameter" and calc_name in paramList:
                        pass
                    else:
                        calcList.append(list(calc_row))

    # convert the list of calcs into a data frame
    data = calcList
    #data.sort()
    # list(data for data, _ in itertools.groupby(data))
    data_dedup = [data[i] for i in range(len(data)) if i == 0 or data[i] != data[i - 1]]

    return data_dedup

# translate the text in a twb
def translate_twb(file,src,dest,hashid):
    translator = google_translator()
    # parse the twb file
    tree = ET.parse(file)
    root = tree.getroot()

   # dictionary of translations
    dict = {}

 # translate sheet names
    for child in root.findall('./worksheets/worksheet'):
        # replace some symbols e.g. _ with spaces
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    for child in root.findall('./dashboards/dashboard/zone'):
        if child.get('name') is not None:
            clean_text = child.get('name').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('name')] = new_text
            child.attrib['name'] = new_text

    for child in root.findall('./dashboards/dashboard/zones'):
        for subchild in child.iter('zone'):
            if subchild.get('name') is not None:
                clean_text = subchild.get('name').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[subchild.get('name')] = new_text
                subchild.attrib['name'] = new_text

    for subroot in root.findall('./dashboards/dashboard/devicelayouts/devicelayout/zones'):
        for child in subroot.iter('zone'):
            if child.get('name') is not None:
                clean_text = child.get('name').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('name')] = new_text
                child.attrib['name'] = new_text

    for child in root.iter('viewpoint'):
        if child.get('name') is not None:
            clean_text = child.get('name').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('name')] = new_text
            child.attrib['name'] = new_text

    for child in root.iter('story-point'):
        if child.get('captured-sheet') is not None:
            clean_text = child.get('captured-sheet').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('captured-sheet')] = new_text
            child.attrib['captured-sheet'] = new_text

    # translate dashboard and story names
    for child in root.findall('./dashboards/dashboard'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    # translate story point titles
    for child in root.iter('story-point'):
        clean_text = child.get('caption').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('caption')] = new_text
        child.attrib['caption'] = new_text

    # translate all text objects, including dashboard and story point text boxes,
    # sheet captions, and custom filter titles on dashboards
    for child in root.iter('run'):
        if not (child.text.startswith('<') or child.text.startswith('&')
                or child.text.startswith('Æ') or '.[Multiple Values]' in child.text
                or child.text.startswith('[') or '[federated' in child.text):
            # replace some symbols e.g. _ with spaces
            clean_text = child.text.replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            dict[child.text] = trans_obj
            child.text = trans_obj

    for child in root.iter('format'):
        if child.get('attr') == 'title' and len(child.get('value')) > 1:
            #replace some symbols e.g. _ with spaces
            clean_text = child.get('value').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            dict[child.get('value')] = trans_obj
            child.attrib['value'] = trans_obj

    # translate renamed fields, calculated fields, and parameters
    # for upchild in root.findall('./datasources/datasource'):
    #     childs = upchild.iter('column')
    #     for child in childs:
    #         if child.get('caption') is not None:
    #             clean_text = child.get('caption').replace('_', ' ')
    #             trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
    #             new_text = trans_obj
    #             dict[child.get('caption')] = new_text
    #             child.attrib['caption'] = new_text
    #         else:
    #             clean_text = child.get('name').replace('_', ' ')
    #             clean_text = clean_text.replace('[', '')
    #             clean_text = clean_text.replace(']', '')
    #             trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
    #             new_text = trans_obj
    #             child.attrib['caption'] = new_text

    for child in root.findall('./datasources/datasource/column'):
        if child.get('alias') is not None:
            clean_text = child.get('alias').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('alias')] = new_text
            child.attrib['alias'] = new_text

    for child in root.findall('./datasources/datasource/column/aliases/alias'):
        if child.get('value') is not None:
            clean_text = child.get('value').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('value')] = new_text
            child.attrib['value'] = new_text

    for child in root.findall('./datasources/datasource/column/members/member'):
        if child.get('alias') is not None:
            clean_text = child.get('alias').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('alias')] = new_text
            child.attrib['alias'] = new_text

    for child in root.findall('./datasources/datasource/datasource-dependencies/column'):
        if child.get('alias') is not None:
            clean_text = child.get('alias').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('alias')] = new_text
            child.attrib['alias'] = new_text

    for child in root.findall('./datasources/datasource/datasource-dependencies/column/aliases/alias'):
        if child.get('value') is not None:
            clean_text = child.get('value').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('value')] = new_text
            child.attrib['value'] = new_text

    for child in root.findall('./datasources/datasource/datasource-dependencies/members/member'):
        if child.get('alias') is not None:
            clean_text = child.get('alias').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('alias')] = new_text
            child.attrib['alias'] = new_text

    for child in root.findall('./worksheets/worksheet/table/view/datasource-dependencies/column'):
        if child.get('caption') is not None:
            if child.get('caption') in dict:
                child.attrib['caption'] = dict[child.get('caption')]
            else:
                clean_text = child.get('caption').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('caption')] = new_text
                child.attrib['caption'] = new_text
        else:
            if child.get('name') is not None:
                clean_text = child.get('name').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('name')] = new_text
                child.attrib['caption'] = new_text

    # # create a list of fields in each ds
    # for parent in root.findall('./datasources/datasource'):
    #     view_cols = []
    #     datasource = parent.get('name')
    #     for child in parent.iter('local-name'):
    #         view_cols.append(child.text)
    #     ds_view_cols[datasource] = view_cols

    # for ds, cols in ds_ds_cols.items():
    #     for key in cols:
    #         print(ds + '- ', key + ': ', cols[key])

    for child in root.iter('column'):
        if child.get('caption') is not None:
            if child.get('caption') in dict:
                child.attrib['caption'] = dict[child.get('caption')]
            else:
                clean_text = child.get('caption').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('caption')] = new_text
                child.attrib['caption'] = new_text
        else:
            if child.get('name') is not None:
                clean_text = child.get('name').replace('_', ' ')
                clean_text = clean_text.replace('[', '')
                clean_text = clean_text.replace(']', '')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('name')] = new_text
                child.attrib['caption'] = new_text

    # for child in root.iter('metadata-record'):
    #     if child.get('class') == 'column':
    #         for subchild in child.findall('remote-alias'):
    #             if subchild.text is not None:
    #                 if subchild.text in dict:
    #                     subchild.text = dict[subchild.text]
    #                 else:
    #                     s = subchild.text
    #                     clean_text = s.replace('_', ' ')
    #                     trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
    #                     new_text = trans_obj
    #                     dict[subchild.text] = new_text
    #                     subchild.text = new_text
    #
    # translate groups and bins
    for child in root.findall('./datasources/datasource/column'):
        for tag in child.findall('calculation[@class]'):
            if tag.get('class') == 'categorical-bin' or tag.get('class') == 'bin':
                if child.get('caption') is not None:
                    clean_text = child.get('caption').replace('_', ' ')
                    trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                    new_text = trans_obj
                    dict[child.get('caption')] = new_text
                    child.attrib['caption'] = new_text

    # # translate custom group dimensions
    # for subroot in root.iter('calculation'):
    #     if subroot.get('class') == 'categorical-bin':
    #         for child in subroot.findall('bin'):
    #             if child.get('default-name') == 'false':
    #                 clean_text = child.get('value').replace('_', ' ')
    #                 trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
    #                 new_text = trans_obj
    #                 dict[child.get('value')] = new_text
    #                 child.attrib['value'] = new_text

    # translate sets
    for child in root.findall('./datasources/datasource/group'):
        if child.get('caption') is not None:
            clean_text = child.get('caption').replace('_', ' ')
            trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            new_text = trans_obj
            dict[child.get('caption')] = new_text
            child.attrib['caption'] = new_text
            # clean_text = child.get('name').replace('_', ' ')
            # clean_text = clean_text.replace('[', '')
            # clean_text = clean_text.replace(']', '')
            # trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
            # new_text = trans_obj
            # dict[child.get('name')] =  '[' + new_text + ']'
            # child.attrib['name'] = '[' + new_text + ']'

    for child in root.findall('./datasources/datasource/group/groupfilter/groupfilter'):
        if child.get('function') == 'reference':
            if child.get('field') is not None:
                clean_text = child.get('field').replace('_', ' ')
                clean_text = clean_text.replace('[', '')
                clean_text = clean_text.replace(']', '')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('field')] = '[' + new_text + ']'
                child.attrib['field'] = '[' + new_text + ']'

    # translate folders
    for child in root.findall('./datasources/datasource/*folder'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    for child in root.findall('./datasources/datasource/*/folder'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    # update parameter dependencies
    for child in root.findall('./datasources/datasource/datasource-dependencies/column'):
        clean_text = child.get('caption').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('caption')] = new_text
        child.attrib['caption'] = new_text

    # update windows
    for child in root.findall('./windows/window'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    # update thumbnails
    for child in root.findall('./thumbnails/thumbnail'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
        new_text = trans_obj
        dict[child.get('name')] = new_text
        child.attrib['name'] = new_text

    # translate Action filters
    for child in root.findall('./worksheets/worksheet/table/view/filter'):
        if child.get('column') is not None:
            s = child.get('column')
            pre_action_text = (re.search(r'(?<=\[).*?(?=\])', s).group(0))
            action_text = (re.search(r'(?<=\.\[).*?(?=\])', s).group(0))
            if action_text.startswith('Action '):
                action_field_list = re.search(r'(?<=\().*?(?=\))', s).group(0)
                action_field_list = action_field_list.split(',')
                translated_list = []
                for item in action_field_list:
                    if item in dict:
                        translated_list.append(dict[item])
                    else:
                        translated_list.append(item)
                new_text = '[' + pre_action_text + '].[' + 'Action (' + ','.join(translated_list) + ')]'
                dict[child.get('column')] = new_text
                child.attrib['column'] = new_text

    for child in root.findall('./datasources/datasource/group'):
        if child.get('name').startswith('[Action ('):
            s = child.get('name')
            action_text = (re.search(r'(?<=\[).*?(?=\])', s).group(0))
            if action_text.startswith('Action '):
                action_field_list = re.search(r'(?<=\().*?(?=\))', s).group(0)
                action_field_list = action_field_list.split(',')
                translated_list = []
                for item in action_field_list:
                    if item in dict:
                        translated_list.append(dict[item])
                    else:
                        translated_list.append(item)
                new_text = '[' + 'Action (' + ','.join(translated_list) + ')]'
                dict[child.get('name')] = new_text
                child.attrib['name'] = new_text

    for child in root.findall('./worksheets/worksheet/table/view/slices/column'):
        s = child.text
        pre_action_text = (re.search(r'(?<=\[).*?(?=\])', s).group(0))
        action_text = (re.search(r'(?<=\.\[).*?(?=\])', s).group(0))
        if action_text.startswith('Action '):
            action_field_list = re.search(r'(?<=\().*?(?=\))', s).group(0)
            action_field_list = action_field_list.split(',')
            translated_list = []
            for item in action_field_list:
                if item in dict:
                    translated_list.append(dict[item])
                else:
                    translated_list.append(item)
            new_text = '[' + pre_action_text + '].[' + 'Action (' + ','.join(translated_list) + ')]'
            dict[child.text] = new_text
            child.text = new_text

    for child in root.findall('actions/action/source'):
        if child.get('dashboard') is not None:
            if child.get('dashboard') in dict:
                child.attrib['dashboard'] = dict[child.get('dashboard')]
            else:
                clean_text = child.get('dashboard').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('dashboard')] = new_text
                child.attrib['dashboard'] = new_text
        if child.get('worksheet') is not None:
            if child.get('worksheet') in dict:
                child.attrib['worksheet'] = dict[child.get('worksheet')]
            else:
                clean_text = child.get('worksheet').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('worksheet')] = new_text
                child.attrib['worksheet'] = new_text

    for child in root.iter('exclude-sheet'):
        if child.get('name') is not None:
            if child.get('name') in dict:
                child.attrib['name'] = dict[child.get('name')]
            else:
                clean_text = child.get('name').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('name')] = new_text
                child.attrib['name'] = new_text

    for child in root.findall('actions/action/command/param'):
        if child.get('name') == 'target':
            if child.get('value') in dict:
                child.attrib['value'] = dict[child.get('value')]
            else:
                clean_text = child.get('value').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('value')] = new_text
                child.attrib['value'] = new_text
        elif child.get('name') == 'exclude':
            if child.get('value') in dict:
                child.attrib['value'] = dict[child.get('value')]
            else:
                clean_text = child.get('value').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('value')] = new_text
                child.attrib['value'] = new_text
        elif child.get('name') == 'exclude':
            if child.get('value') in dict:
                child.attrib['value'] = dict[child.get('value')]
            else:
                clean_text = child.get('value').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('value')] = new_text
                child.attrib['value'] = new_text

        elif child.get('name') == 'exclude':
            if child.get('value') in dict:
                child.attrib['value'] = dict[child.get('value')]
            else:
                clean_text = child.get('value').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('value')] = new_text
                child.attrib['value'] = new_text
        elif child.get('name') == 'field-captions':
            if child.get('value') in dict:
                child.attrib['value'] = dict[child.get('value')]
            else:
                clean_text = child.get('value').replace('_', ' ')
                trans_obj = translator.translate(clean_text, lang_src=src, lang_tgt=dest)
                new_text = trans_obj
                dict[child.get('value')] = new_text
                child.attrib['value'] = new_text

    for child in root.findall('actions/action/link'):
        if child.get('expression') is not None:
            s = child.get('expression')
            snip = re.search(r'(?<=:).*?(?=\?)', s)
            if snip is not None:
                snip = snip.group(0)
                url_decode_snip = urllib.parse.unquote(snip)
                if url_decode_snip in dict:
                    translated_snip = dict[url_decode_snip]
                    url_enc_translated_snip = urllib.parse.quote(translated_snip)
                    translated_s = s.replace(snip, url_enc_translated_snip)
                    dict[child.get('expression')] = translated_s
                    child.attrib['expression'] = translated_s
                else:
                    trans_obj = translator.translate(url_decode_snip, lang_src=src, lang_tgt=dest)
                    translated_snip = trans_obj
                    url_enc_translated_snip = urllib.parse.quote(translated_snip)
                    translated_s = s.replace(snip, url_enc_translated_snip)
                    dict[child.get('expression')] = translated_s
                    child.attrib['expression'] = translated_s

    output = os.path.join(app.config['OUTPUT_FOLDER'], hashid)
    tree.write(output+'.twb', encoding="UTF-8")

if __name__ == "__main__":
    app.run()
