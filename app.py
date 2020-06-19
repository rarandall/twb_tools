import os
from flask import Flask, redirect, render_template, request, session, Response
import uuid
from werkzeug.utils import secure_filename
import xml.etree.ElementTree as ET
import pandas as pd
import re

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'twb'}
UPLOAD_FOLDER = '/Users/p-73/PycharmProjects/flask/myproject/upload/'

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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
            filename = secure_filename(file.filename)
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

if __name__ == "__main__":
    app.secret_key = 'AoAv38dAf3A0ZTvE392jdjsvRBKN72v765f?RT'
    app.run()