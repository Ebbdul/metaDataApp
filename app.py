# -*- coding: utf-8 -*-
"""
Created on Tue Aug 15 17:04:05 2023

@author: m.umer, abdul.wasay
"""

from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import re
import psycopg2 
import warnings
import pyodbc 
import mysql.connector
warnings.filterwarnings('ignore')

app = Flask(__name__)
app.secret_key = b'6hc/_gsh,./;2ZZx3c6_s,1//'

def QueryToDataFrame(Query, Connection):
    DataFrame=pd.read_sql(Query, Connection)
    return DataFrame

def DataBaseConnection(Query, DataBase, Address, Port, UserName, Password, DatabaseName=''):
    if DataBase == "postgres":
        if DatabaseName != '':
            Connection = psycopg2.connect(host=Address, port=Port, user=UserName, password=Password, dbname=DatabaseName)
        else:
            Connection = psycopg2.connect(host=Address, port=Port, user=UserName, password=Password)
    elif DataBase == "sql_server":
        if DatabaseName != '':
            Connection =pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+Address+';UID='+UserName+';PWD='+ Password)
        else:
            Connection =pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+Address+';DATABASE='+DatabaseName+';UID='+UserName+';PWD='+ Password)
    elif DataBase == "mysql":
        if DatabaseName != '':
            Connection = mysql.connector.connect( host=Address, port=Port, user=UserName, password=Password)
        else:
            Connection = mysql.connector.connect( host=Address, port=Port, user=UserName, password=Password, database=DatabaseName)
    ResultedDataframe = QueryToDataFrame(Query, Connection)
    Connection.close()
    return ResultedDataframe

def DatabaseList(ResultedDataframe):
    return ResultedDataframe['databases'].to_list()

def SchemaList(ResultedDataframe):
    return ResultedDataframe['schemas'].to_list()

def DataFrameToColNVal(DataFrame):
    Columns = DataFrame.to_dict('records')
    Values= DataFrame.columns.values
    return Columns, Values


def ProceduresList(ResultedDataframe):
    return ResultedDataframe['ProcedureName'].to_list()

def SearchStringFromProcedure(SearchString, Procedure):
    #SpecificKeywords = ['INSERT', 'SELECT', 'UPDATE', 'FROM', 'WHERE', 'IN', 'ON', 'VALUES', ',', '\n']
    Occurrences = [line.lower().strip() for line in Procedure.splitlines() if re.search(r'\b' + re.escape(SearchString.lower()) + r'\b', line, re.IGNORECASE)]
    #ResultedLines = [line for line in Occurrences if any(line.strip().upper().startswith(keyword) for keyword in SpecificKeywords)]
    return Occurrences

def SearchFromProcedures(DataFrame, InputSearch):
    DataFrame.columns = DataFrame.columns.str.lower()
    ProcedureDict = DataFrame.to_dict('records')
    ResponceDict=[]
    for i in ProcedureDict:
        Lines = SearchStringFromProcedure(InputSearch, i['definition'])
        if len(Lines)>0:
            for idx, line in enumerate(Lines, start=1):
                JsonData={'Type':i['type'],'Name':i['name'], 'String':InputSearch, 'Exist':str(line)}
                ResponceDict.append(JsonData)
    return pd.DataFrame.from_dict(ResponceDict)
        

def FilterFromDB(DataBase, Address, Port, UserName, Password, DatabaseName, InputSearch):
    if DataBase == "postgres":
        Query = '''SELECT  CONCAT(r.routine_schema, '.', r.routine_name) AS Name,  pg_get_functiondef(p.oid) AS Definition,  'PROCEDURE' AS Type FROM information_schema.routines r JOIN pg_proc p ON r.routine_name = p.proname WHERE r.routine_type = 'PROCEDURE'  AND r.routine_schema NOT IN ('pg_catalog', 'information_schema') 
        union all
        SELECT  CONCAT(c.table_schema, '.', t.table_name) AS Name,  c.column_name AS Definition,'Table' AS Type FROM information_schema.columns c JOIN information_schema.tables t ON c.table_schema = t.table_schema AND c.table_name = t.table_name WHERE t.table_schema NOT LIKE 'pg_%' AND t.table_schema NOT LIKE 'information_schema'
        union all
        SELECT distinct CONCAT(r.routine_schema, '.', r.routine_name) AS Name,  pg_get_functiondef(p.oid) AS Definition,  'Function' AS Type FROM information_schema.routines r JOIN pg_proc p ON r.routine_name = p.proname WHERE r.routine_type = 'FUNCTION' AND r.routine_schema NOT IN ('pg_catalog', 'information_schema') 
        union all
        SELECT CONCAT(table_schema, '.', table_name)  AS Name, view_definition AS Definition,  'View' AS Type FROM information_schema.views WHERE table_schema NOT IN ('pg_catalog', 'information_schema');
        '''
    elif DataBase == "sql_server":
        Query = '''SELECT CONCAT(SCHEMA_NAME(o.schema_id), '.', o.name) AS Name, m.definition AS Definition, 'PROCEDURE' AS Type FROM sys.objects AS o JOIN sys.sql_modules AS m ON o.object_id = m.object_id WHERE o.type = 'P'   
        UNION ALL
        SELECT CONCAT(SCHEMA_NAME(o.schema_id), '.', o.name) AS Name, c.name AS Definition, 'TABLE' AS Type FROM sys.objects AS o JOIN sys.columns AS c ON o.object_id = c.object_id WHERE o.type = 'U'
        UNION ALL
        SELECT CONCAT(SCHEMA_NAME(o.schema_id), '.', o.name) AS Name, m.definition AS Definition, 'FUNCTION' AS Type FROM sys.objects AS o JOIN sys.sql_modules AS m ON o.object_id = m.object_id WHERE o.type = 'FN'
        UNION ALL
        SELECT CONCAT(SCHEMA_NAME(o.schema_id), '.', o.name) AS Name, m.definition AS Definition, 'VIEW' AS Type FROM sys.objects AS o JOIN sys.sql_modules AS m ON o.object_id = m.object_id WHERE o.type = 'V';  '''
    elif DataBase == "mysql":
        Query = ''' SELECT CONCAT(ROUTINE_SCHEMA, '.', ROUTINE_NAME) AS Name, ROUTINE_DEFINITION AS Definition,  'PROCEDURE' AS Type FROM information_schema.routines WHERE ROUTINE_TYPE = 'PROCEDURE'
        union all
        SELECT CONCAT(TABLE_SCHEMA, '.', TABLE_NAME) AS Name, COLUMN_NAME AS Definition, 'Table' AS Type FROM information_schema.columns WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        union all
        SELECT CONCAT(ROUTINE_SCHEMA, '.', ROUTINE_NAME) AS Name, ROUTINE_DEFINITION AS Definition, 'Function' AS Type FROM information_schema.routines WHERE ROUTINE_TYPE = 'FUNCTION'
        union all
        SELECT CONCAT(TABLE_SCHEMA, '.', TABLE_NAME) AS Name, VIEW_DEFINITION AS Definition, 'View' AS Type FROM information_schema.views'''
    ContentDataFrame = DataBaseConnection(Query, DataBase, Address, Port, UserName, Password, DatabaseName)
    ResultedDataFrame = SearchFromProcedures(ContentDataFrame, InputSearch)
    return ResultedDataFrame
    

@app.route('/')
def index():
    return render_template('Main.html')

@app.route('/submit_main_form', methods=['Post'])
def submit_main_form():
    try:
        DataBase = request.form['database']
        session['DataBase'] = DataBase
        Address = request.form['ip_address']
        session['Address'] = Address
        Port = request.form['port']
        session['Port'] = Port
        UserName=request.form['user_name']
        session['UserName'] = UserName
        Password=request.form['password']
        session['Password'] = Password
        if DataBase == "postgres":
            Query = '''SELECT datname as "databases" FROM pg_database WHERE datistemplate = false;'''
        elif DataBase == "sql_server":
            Query = '''SELECT name as "databases"  FROM sys.databases WHERE database_id > 4;'''
        elif DataBase == "mysql":
            Query = ''' SHOW DATABASES as "databases"; '''
        ResultedDataframe = DataBaseConnection(Query, DataBase, Address, Port, UserName, Password)
        DataBasesName = DatabaseList(ResultedDataframe)
        return jsonify({'status':'true','message':'Connection Successful','template':render_template('DataBaseList.html', dbName= DataBasesName)}) 
    except Exception as e:
        return jsonify({'status':'false','message':e})
    
@app.route('/db_data', methods=['Post'])
def db_data():
    DatabaseName = request.form['db_name']
    DataBase = session.get('DataBase', None)
    Address = session.get('Address', None)
    Port = session.get('Port', None)
    UserName = session.get('UserName', None)
    Password = session.get('Password', None)
    session['DatabaseName'] = DatabaseName
    if DataBase == "postgres":
        Query = '''SELECT schema_name as "schemas" FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema';'''
    elif DataBase == "sql_server":
        Query = '''SELECT schema_name(schema_id) AS schemas FROM sys.schemas WHERE schema_id > 4;'''
    elif DataBase == "mysql":
        Query = '''SELECT SCHEMA_NAME as "schemas" FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys'); '''
    ResultedDataframe = DataBaseConnection(Query, DataBase, Address, Port, UserName, Password, DatabaseName)
    SchemaNameList = SchemaList(ResultedDataframe)
    return jsonify({'status':'true','message':'Connection Successful','template':render_template('SchemasList.html', shName = SchemaNameList)}) 

@app.route('/schema_data', methods=['Post'])
def schema_data():
    SchemaName = request.form['sh_name']
    DataBase = session.get('DataBase', None)
    Address = session.get('Address', None)
    Port = session.get('Port', None)
    UserName = session.get('UserName', None)
    Password = session.get('Password', None)
    DatabaseName = session.get('DatabaseName', None)
    session['SchemaName'] = SchemaName
    if DataBase == "postgres":
        TableQuery=''' SELECT table_name as "Name" FROM information_schema.tables WHERE table_schema = '{}' and table_type = 'BASE TABLE' AND table_schema NOT LIKE 'pg_%' AND table_schema != 'information_schema' ORDER BY table_schema, table_name; '''.format(SchemaName)
        ViewQuery = ''' SELECT table_name AS "Name", view_definition as Content FROM information_schema.views WHERE table_schema = '{}' AND table_schema != 'information_schema' AND table_schema != 'pg_catalog'; '''.format(SchemaName)
        UserQuery = '''select usesysid as "Id",usename as "Name",usesuper as "Is SuperUser", passwd as "Password" from pg_shadow order by usename;'''
        ProcedureQuery='''SELECT   r.routine_name AS Name,  pg_get_functiondef(p.oid) AS Content FROM information_schema.routines r JOIN pg_proc p ON r.routine_name = p.proname WHERE r.routine_type = 'PROCEDURE' AND r.routine_schema NOT IN ('pg_catalog', 'information_schema')  AND r.routine_schema = '{}' '''.format(SchemaName)
        FunctionQuery='''SELECT distinct  r.routine_name AS Name,  pg_get_functiondef(p.oid) AS Content FROM information_schema.routines r JOIN pg_proc p ON r.routine_name = p.proname WHERE r.routine_type = 'FUNCTION' AND r.routine_schema NOT IN ('pg_catalog', 'information_schema')  AND r.routine_schema ='{}' '''.format(SchemaName)
    elif DataBase == "sql_server":
        TableQuery=''' SELECT TABLE_NAME as "Name" FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' and TABLE_SCHEMA = '{}'; '''.format(SchemaName)
        ViewQuery = ''' SELECT v.name AS Name, m.definition AS Content FROM sys.views v INNER JOIN sys.schemas s ON v.schema_id = s.schema_id INNER JOIN sys.sql_modules m ON v.object_id = m.object_id where s.name ='{}'; '''.format(SchemaName)
        UserQuery = ''' SELECT name FROM sys.database_principals WHERE type_desc = 'SQL_USER';'''
        ProcedureQuery='''SELECT p.name AS Name, m.definition AS Content FROM sys.procedures p INNER JOIN sys.schemas s ON p.schema_id = s.schema_id INNER JOIN sys.sql_modules m ON p.object_id = m.object_id where s.name ='{}';'''.format(SchemaName)
        FunctionQuery='''SELECT o.name AS Name, m.definition AS Content FROM sys.objects AS o JOIN sys.sql_modules AS m ON o.object_id = m.object_id WHERE o.type = 'FN'  and SCHEMA_NAME(o.schema_id) = '{}';'''.format(SchemaName)
    elif DataBase == "mysql":
        TableQuery=''' SELECT  TABLE_NAME as "Name" FROM  information_schema.TABLES WHERE  TABLE_TYPE = 'BASE TABLE' and  TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') and TABLE_SCHEMA ='{}';'''.format(SchemaName)
        ViewQuery = ''' SELECT table_name AS Name, view_definition AS Content FROM information_schema.views WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') and table_schema ='{}';  '''.format(SchemaName)
        UserQuery = ''' SELECT user, host, authentication_string, plugin, account_locked FROM  mysql.user; '''
        ProcedureQuery='''SELECT routine_name AS Name, ROUTINE_DEFINITION AS Content FROM information_schema.routines WHERE routine_type = 'PROCEDURE' and routine_schema ='{}'; '''.format(SchemaName)
        FunctionQuery='''SELECT routine_name AS Name, ROUTINE_DEFINITION AS Content FROM information_schema.routines WHERE routine_type = 'FUNCTION' and routine_schema ='{}';'''.format(SchemaName)
    Tabletemp, TablecolumnNames = DataFrameToColNVal(DataBaseConnection(TableQuery, DataBase, Address, Port, UserName, Password, DatabaseName))
    Viewtemp, ViewcolumnNames = DataFrameToColNVal(DataBaseConnection(ViewQuery, DataBase, Address, Port, UserName, Password, DatabaseName))
    Proceduretemp,ProcedurecolumnNames  = DataFrameToColNVal(DataBaseConnection(ProcedureQuery, DataBase, Address, Port, UserName, Password, DatabaseName))
    Usertemp,  UsercolumnNames = DataFrameToColNVal(DataBaseConnection(UserQuery, DataBase, Address, Port, UserName, Password, DatabaseName))
    Functiontemp,  FunctioncolumnNames = DataFrameToColNVal(DataBaseConnection(FunctionQuery, DataBase, Address, Port, UserName, Password, DatabaseName))
    return jsonify({'status':'true','message':'Connection Successful','template':render_template('DbDataTabsList.html', Tabletemp=Tabletemp, TablecolumnNames=TablecolumnNames, Viewtemp=Viewtemp, ViewcolumnNames=ViewcolumnNames,ProcedurecolumnNames=ProcedurecolumnNames,Proceduretemp=Proceduretemp,UsercolumnNames=UsercolumnNames,Usertemp=Usertemp, Functiontemp = Functiontemp,  FunctioncolumnNames= FunctioncolumnNames)}) 


@app.route('/search_request', methods=['Post'])
def search_request():
    InputSearch = request.form['inputsearch']
    DataBase = session.get('DataBase', None)
    Address = session.get('Address', None)
    Port = session.get('Port', None)
    UserName = session.get('UserName', None)
    Password = session.get('Password', None)
    DatabaseName = session.get('DatabaseName', None)
    ResultedDataFrame=FilterFromDB(DataBase, Address, Port, UserName, Password, DatabaseName, InputSearch)
    searchtemp, SearchcolumnNames = DataFrameToColNVal(ResultedDataFrame)
    return jsonify({'status':'true','message':'Connection Successful','template':render_template('SearchResult.html', searchtemp = searchtemp, SearchcolumnNames=SearchcolumnNames)}) 
    
@app.route('/columns_view', methods=['Post'])
def columns_view():
    TableName = request.form['table_name']
    DataBase = session.get('DataBase', None)
    Address = session.get('Address', None)
    Port = session.get('Port', None)
    UserName = session.get('UserName', None)
    Password = session.get('Password', None)
    DatabaseName = session.get('DatabaseName', None)
    SchemaName = session.get('SchemaName', None)
    if DataBase == "postgres":
        ColumnsQuery = '''SELECT col.table_schema, col.table_name, col.column_name, col.data_type, CASE WHEN col.column_name IN (SELECT kcu.column_name FROM information_schema.key_column_usage kcu JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'PRIMARY KEY'   AND col.table_name = kcu.table_name) THEN true ELSE false END AS is_primary_key, CASE WHEN col.column_name IN (SELECT kcu.column_name FROM information_schema.key_column_usage kcu JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'FOREIGN KEY'   AND col.table_name = kcu.table_name) THEN true ELSE false END AS is_foreign_key, CASE WHEN col.column_name IN (SELECT kcu.column_name FROM information_schema.key_column_usage kcu JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'UNIQUE'   AND col.table_name = kcu.table_name) THEN true ELSE false END AS is_unique, col.is_nullable FROM information_schema.columns col where col.table_schema = '{}' and col.table_name = '{}' '''.format(SchemaName, TableName)
    elif DataBase == "sql_server":
        ColumnsQuery = ''' SELECT OBJECT_SCHEMA_NAME(c.object_id) AS SchemaName, OBJECT_NAME(c.object_id) AS TableName, c.name AS ColumnName, t.name AS DataType, c.max_length AS MaxLength, c.precision AS Precision, c.scale AS Scale, c.is_nullable AS IsNullable FROM sys.columns AS c JOIN sys.types AS t ON c.system_type_id = t.system_type_id AND c.user_type_id = t.user_type_id WHERE OBJECT_SCHEMA_NAME(c.object_id)='{}' and OBJECT_NAME(c.object_id) = '{}' '''.format(SchemaName, TableName)
    elif DataBase == "mysql":
        ColumnsQuery = ''' SELECT COLUMN_NAME AS ColumnName, DATA_TYPE AS DataType, COLUMN_KEY AS ColumnKey, REFERENCED_TABLE_SCHEMA AS ReferencedSchema, REFERENCED_TABLE_NAME AS ReferencedTable, REFERENCED_COLUMN_NAME AS ReferencedColumn FROM information_schema.columns LEFT JOIN information_schema.key_column_usage ON columns.TABLE_SCHEMA = key_column_usage.TABLE_SCHEMA AND columns.TABLE_NAME = key_column_usage.TABLE_NAME AND columns.COLUMN_NAME = key_column_usage.COLUMN_NAME WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') and TABLE_SCHEMA ='{}' and TABLE_NAME='{}';'''.format(SchemaName, TableName)
    ColumnsDataFrame = DataBaseConnection(ColumnsQuery, DataBase, Address, Port, UserName, Password, DatabaseName)
    ColumnsTemp, ColumnNames = DataFrameToColNVal(ColumnsDataFrame)
    return jsonify({'status':'true','message':'Connection Successful','template':render_template('ColumnsInformation.html', ColumnsTemp=ColumnsTemp, ColumnNames=ColumnNames)}) 

if __name__ == '__main__':
    app.run(host='0.0.0.0' , port=5000)
