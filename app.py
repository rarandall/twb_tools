import os
from flask import Flask, render_template, request, session, Response, send_from_directory, current_app
import uuid
from werkzeug.utils import secure_filename
from xml.etree.ElementTree import tostring
import xml.etree.ElementTree as ET
from googletrans import Translator
import pandas as pd
import re

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'twb'}
UPLOAD_FOLDER = '/Users/p-73/PycharmProjects/flask/myproject/upload/'
OUTPUT_FOLDER = '/Users/p-73/PycharmProjects/flask/myproject/output/'

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_PATH'] = 50000

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
            p_df = pd.DataFrame(df, columns=['Name', 'Remote_Name', 'Formula', 'Comment'])
            fields = get_fields(p_df)
            paths = get_paths(p_df)
            return render_template('output.html', filename=df, fileid=filename_h, fields=fields, paths=paths)
        else:
            error = "Not a valid twb file"
            return render_template('upload.html', error=error)
    return render_template('upload.html')

@app.route("/csv", methods=['POST'])
def csv():
    if request.method == 'POST':
        f = request.form.get("fileid")
        lol = get_calc(UPLOAD_FOLDER+f)
        df = pd.DataFrame(lol, columns=['Name', 'Remote_Name', 'Formula', 'Comment'])
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
        file = request.files['file1']
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

def get_calc(file):
    # parse the twb file
    tree = ET.parse(file)
    root = tree.getroot()

    # create a dictionary of name and tableau generated name

    calcDict = {}

    for item in root.findall('.//column[@caption]'):
        if item.find(".//calculation") is None:
            continue
        else:
            calcDict[item.attrib['name']] = '[' + item.attrib['caption'] + ']'

    # list of calc's name, tableau generated name, and calculation/formula
    calcList = []

    for item in root.findall('.//column[@caption]'):
        if item.find(".//calculation") is None:
            continue
        else:
            if item.find(".//calculation[@formula]") is None:
                continue
            else:
                calc_caption = '[' + item.attrib['caption'] + ']'
                calc_name = item.attrib['name']
                calc_raw_formula = item.find(".//calculation").attrib['formula']
                calc_comment = ''
                calc_formula = ''
                for line in calc_raw_formula.split('\r\n'):
                    if line.startswith('//'):
                        calc_comment = calc_comment + line + ' '
                    else:
                        calc_formula = calc_formula + line + ' '
                for name, caption in calcDict.items():
                    calc_formula = calc_formula.replace(name, caption)

                calc_row = (calc_caption, calc_name, calc_formula, calc_comment)
                calcList.append(list(calc_row))

    # convert the list of calcs into a data frame
    data = calcList
    data.sort()
    # list(data for data, _ in itertools.groupby(data))
    data_dedup = [data[i] for i in range(len(data)) if i == 0 or data[i] != data[i - 1]]
    # data = pd.DataFrame(data, columns=['Name', 'Remote Name', 'Formula', 'Comment'])

    # remove duplicate rows from data frame
    # data = data.drop_duplicates(subset=None, keep='first', inplace=False)

    # export to csv
    # get the name of the file

    #base = os.path.basename(file)
    #os.path.splitext(base)
    #filename = os.path.splitext(base)[0]

    #data.to_csv(filename + '.csv')
    return data_dedup

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
        s = s.replace('[Parameters].[', '[Parameter: ')
        formula_fields = re.findall('\[.*?\]', s)
        for field in formula_fields:
            kv = {}
            for dict in key_dict:
                if dict.get('text') == field.replace('[Parameters].[', '[Parameter: '):
                    kv['from'] = dict.get('key')
                if dict.get('text') == df.iloc[i]['Name']:
                    kv['to'] = dict.get('key')
                    kv['text'] = 'o'
            if len(kv) == 3 and kv not in paths_kvs:
                paths_kvs.append(kv)
    return paths_kvs

# translate the text in a twb
def translate_twb(file,src,dest,hashid):
    translator = Translator()
    # parse the twb file
    tree = ET.parse(file)
    root = tree.getroot()

    # translate sheet names
    for child in root.findall('./worksheets/worksheet'):
        # replace some symbols e.g. _ with spaces
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    # translate dashboard and story names
    for child in root.findall('./dashboards/dashboard'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    # translate story point titles
    for child in root.iter('story-point'):
        clean_text = child.get('caption').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['caption'] = new_text

    # translate all text objects, including dashboard and story point text boxes,
    # sheet captions, and custom filter titles on dashboards
    for child in root.iter('run'):
        # replace some symbols e.g. _ with spaces
        clean_text = child.text.replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        child.text = trans_obj.text

    # translate renamed fields, calculated fields, and parameters
    for child in root.findall('./datasources/*/column'):
        if child.get('caption') is not None:
            clean_text = child.get('caption').replace('_', ' ')
            trans_obj = translator.translate(clean_text, src=src, dest=dest)
            new_text = trans_obj.text
            child.attrib['caption'] = new_text

    # translate groups and bins
    for child in root.findall('./datasources/datasource/column'):
        for tag in child.findall('calculation[@class]'):
            if tag.get('class') == 'categorical-bin' or tag.get('class') == 'bin':
                if child.get('caption') is None:
                    clean_text = child.get('name').replace('_', ' ')
                    trans_obj = translator.translate(clean_text, src=src, dest=dest)
                    new_text = trans_obj.text
                    child.attrib['name'] = new_text
                else:
                    clean_text = child.get('caption').replace('_', ' ')
                    trans_obj = translator.translate(clean_text, src=src, dest=dest)
                    new_text = trans_obj.text
                    child.attrib['caption'] = new_text

    # translate sets
    # for child in root.findall('./datasources/datasource/group'):
    #     if child.get('caption') is not None:
    #         clean_text = child.get('caption').replace('_', ' ')
    #         trans_obj = translator.translate(clean_text, src=src, dest=dest)
    #         new_text = trans_obj.text
    #         child.attrib['caption'] = new_text
    #         child.attrib['name'] = '['+new_text+']'

    # translate folders
    for child in root.findall('./datasources/datasource/*folder'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    for child in root.findall('./datasources/datasource/*/folder'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    # update parameter dependencies
    for child in root.findall('./datasources/datasource/datasource-dependencies/column'):
        clean_text = child.get('caption').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['caption'] = new_text

    # update windows
    for child in root.findall('./windows/window'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    # update thumbnails
    for child in root.findall('./thumbnails/thumbnail'):
        clean_text = child.get('name').replace('_', ' ')
        trans_obj = translator.translate(clean_text, src=src, dest=dest)
        new_text = trans_obj.text
        child.attrib['name'] = new_text

    output = os.path.join(app.config['OUTPUT_FOLDER'], hashid)
    tree.write(output+'.twb')

if __name__ == "__main__":
    app.secret_key = 'AoAv38dAf3A0ZTvE392jdjsvRBKN72v765f?RT'
    app.run()