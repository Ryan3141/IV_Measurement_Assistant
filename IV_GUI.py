
import sys
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG
from PyQt5 import QtCore

import configparser
import time
import sqlite3

from Install_If_Necessary import Ask_For_Install
try:
	import mysql.connector
except:
	Ask_For_Install( "mysql-connector-python" )
	import mysql.connector

from IV_Measurement_Assistant import IV_Controller

def resource_path( relative_path ):
	return relative_path


Ui_MainWindow, QtBaseClass = uic.loadUiType( resource_path("IV_GUI.ui") )

def Popup_Error( title, message ):
	error = QtWidgets.QMessageBox()
	error.setIcon( QtWidgets.QMessageBox.Critical )
	error.setText( message )
	error.setWindowTitle( title )
	error.exec_()
	return

def Connect_To_SQL( configuration_file ):
	db_type = configuration_file['SQL_Server']['database_type']
	try:
		if db_type == "QSQLITE":
			sql_conn = sqlite3.connect( configuration_file['SQL_Server']['database_name'] )
		elif db_type == "QMYSQL":
			sql_conn = mysql.connector.connect(host=configuration_file['SQL_Server']['host_location'],database=configuration_file['SQL_Server']['database_name'],
								user=configuration_file['SQL_Server']['username'],password=configuration_file['SQL_Server']['password'])
			sql_conn.ping( True ) # Maintain connection to avoid timing out
		return db_type, sql_conn
	except sqlite3.Error as e:
		error = QtWidgets.QMessageBox()
		error.setIcon( QtWidgets.QMessageBox.Critical )
		error.setText( str(e) )
		error.setWindowTitle( "Unable to connect to SQL Database" )
		error.exec_()
		return None, None
	except mysql.connector.Error as e:
		error = QtWidgets.QMessageBox()
		error.setIcon( QtWidgets.QMessageBox.Critical )
		error.setText( str(e) )
		error.setWindowTitle( "Unable to connect to SQL Database" )
		error.exec_()
		return None, None

def Commit_To_SQL( sql_type, sql_conn, x_data, y_data, sample_name, user, temperature_in_k, measurement_setup, location_x, location_y ):
	get_measurement_id_string = '''SELECT MAX(measurement_id) FROM mpl.iv_measurements'''
	if sql_type == 'QSQLITE':
		meta_data_sql_string = '''INSERT INTO iv_measurements(sample_name,user,temperature_in_k,measurement_setup,location_x,location_y,time)
									VALUES(?,?,?,?,?,?,now())'''
		data_sql_string = '''INSERT INTO raw_iv_data(measurement_id,voltage_v,current_a) VALUES(?,?,?)'''
	else:
		meta_data_sql_string = '''INSERT INTO iv_measurements(sample_name,user,temperature_in_k,measurement_setup,location_x,location_y,time)
									VALUES(%s,%s,%s,%s,%s,%s,now());'''
		data_sql_string = '''INSERT INTO iv_raw_data(measurement_id,voltage_v,current_a) VALUES(%s,%s,%s)'''

	cur = sql_conn.cursor()
	cur.execute( meta_data_sql_string, (sample_name, user, temperature_in_k, measurement_setup, location_x, location_y) )
	cur.execute( get_measurement_id_string )
	measurement_id = int( cur.fetchone()[0] )
	data_as_tuple = tuple(zip([measurement_id] * len(x_data),(float(x) for x in x_data),(float(y) for y in y_data))) # mysql.connector requires a tuple or list (not generator) and native float type as input
	cur.executemany( data_sql_string, data_as_tuple )
	sql_conn.commit()


class IV_Measurement_Assistant_App(QWidget, Ui_MainWindow):
	measurementRequested_signal = QtCore.pyqtSignal(float, float, float)

	def __init__(self, parent=None, root_window=None):
		QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		self.current_data = None

		self.Init_Subsystems()
		self.iv_controller = IV_Controller()
		self.iv_controller_thread = QtCore.QThread()
		self.iv_controller.moveToThread( self.iv_controller_thread )
		self.iv_controller_thread.started.connect( self.iv_controller.run )

		self.Connect_Functions()

		self.iv_controller_thread.start()


	def Init_Subsystems(self):
		configuration_file = configparser.ConfigParser()
		configuration_file.read( resource_path( "configuration.ini" ) )

		self.iv_communications = None
		self.sql_type, self.sql_connection = Connect_To_SQL( configuration_file )

		user = configuration_file['SQL_Server']['user']
		if user:
			self.user_lineEdit.setText( user )


	def Connect_Functions( self ):
		#self.establishComms_pushButton.clicked.connect( self.Establish_Comms )
		self.takeMeasurement_pushButton.clicked.connect( self.Take_Measurement )
		self.outputToFile_pushButton.clicked.connect( self.Save_Data_To_File )
		self.saveToDatabase_pushButton.clicked.connect( self.Save_Data_To_Database )

		self.measurementRequested_signal.connect( self.iv_controller.Voltage_Sweep )
		self.iv_controller.ivControllerConnected_signal.connect( lambda : self.ivConnectionStateChanged(True) )
		self.iv_controller.ivControllerDisconnected_signal.connect( lambda : self.ivConnectionStateChanged(False) )
		self.iv_controller.newSweepStarted_signal.connect( self.iv_Graph.new_plot )
		self.iv_controller.dataPointGotten_signal.connect( self.iv_Graph.add_new_data_point )

		self.iv_controller.sweepFinished_signal.connect( self.Set_Current_Data )

	def Set_Current_Data( self, x_data, y_data ):
		self.current_data = ( x_data, y_data )

	def ivConnectionStateChanged( self, connected_or_disconnected ):
		if connected_or_disconnected:
			pass

	def Establish_Comms( self ):
		self.iv_communications = IV_Measurement_Assistant.Initialize_Connection()

	def Take_Measurement( self ):
		input_start = float( self.start_lineEdit.text() )
		input_end = float( self.end_lineEdit.text() )
		input_step = float( self.step_lineEdit.text() )
		self.measurementRequested_signal.emit( input_start, input_end, input_step )
		#QMetaObject.invokeMethod( self.iv_controller, 'Voltage_Sweep', Qt.AutoConnection,
		#				  Q_RETURN_ARG('int'), Q_ARG(float, input_start), Q_ARG(float, input_end), Q_ARG(float, input_step) )
		#self.recent_results = (input_start = -1, input_end = 1, input_step = 0.01)

	def Save_Data_To_File( self ):
		if self.sampleName_lineEdit.text() == '':
			Popup_Error( "Error", "Must enter sample name" )
			return

		timestr = time.strftime("%Y%m%d-%H%M%S")
		sample_name = str( self.sampleName_lineEdit.text() )
		location_x = str( self.xLocation_lineEdit.text() )
		location_y = str( self.yLocation_lineEdit.text() )

		file_name = "IV Data_" + sample_name + "_" + str(location_x) + "_" + str(location_y) + "_" + timestr + ".csv"
		print( "Saving File: " + file_name )
		with open( file_name, 'w' ) as outfile:
			outfile.write( ','.join([str(x) for x in self.current_data[0]]) + '\n' )
			outfile.write( ','.join([str(x) for x in self.current_data[1]]) + '\n' )

	def Save_Data_To_Database( self ):
		if self.current_data == None:
			return

		sample_name = str( self.sampleName_lineEdit.text() )
		user = str( self.user_lineEdit.text() )
		location_x = float( self.xLocation_lineEdit.text() )
		location_y = float( self.yLocation_lineEdit.text() )
		if sample_name == ''  or user == '':
			Popup_Error( "Error", "Must enter sample name and user" )
			return
		Commit_To_SQL( sql_type=self.sql_type, sql_conn=self.sql_connection, x_data=self.current_data[0], y_data=self.current_data[1],
			   sample_name=sample_name, user=user, temperature_in_k=None, measurement_setup="Microprobe", location_x=location_x, location_y=location_y )
		print( "Data committed to database: " + sample_name + "_" + str(location_x) + "_" + str(location_y) )


if __name__ == '__main__':
	app = QApplication(sys.argv)
	ex = IV_Measurement_Assistant_App()
	ex.show()
	sys.exit(app.exec_())