if __name__ == "__main__": # This allows running this module by running this script
	import pathlib
	import sys
	this_files_directory = pathlib.Path(__file__).parent.resolve()
	sys.path.insert(0, str(this_files_directory.parent.resolve()) ) # Add parent directory to access other modules

from PyQt5 import QtNetwork, QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFileDialog
from PyQt5.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG
from PyQt5 import QtCore
try:
	from PyQt5 import uic
except ImportError:
	import sip
import sys

import numpy as np
import time
import os

from MPL_Shared.Temperature_Controller import Temperature_Controller
from MPL_Shared.Temperature_Controller_Settings import TemperatureControllerSettingsWindow
from MPL_Shared.SQL_Controller import Commit_XY_Data_To_SQL, Connect_To_SQL
from MPL_Shared.IV_Measurement_Assistant import IV_Controller
from MPL_Shared.Async_Iterator import Async_Iterator, Run_Async
from MPL_Shared.Saveable_Session import Saveable_Session
from itertools import product

from MPL_Shared.Pad_Description_File import Get_Device_Description_File

__version__ = '2.00'

base_path = os.path.dirname( os.path.realpath(__file__) )

def resource_path(relative_path = ""):  # Define function to import external files when using PyInstaller.
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return os.path.join(base_path, relative_path)

Ui_MainWindow, QtBaseClass = uic.loadUiType( resource_path("IV_GUI.ui") ) # GUI layout file.

def Popup_Error( title, message ):
	error = QtWidgets.QMessageBox()
	error.setIcon( QtWidgets.QMessageBox.Critical )
	error.setText( message )
	error.setWindowTitle( title )
	error.setStandardButtons( QtWidgets.QMessageBox.Ok )
	return_value = error.exec_()
	return

def Popup_Yes_Or_No( title, message ):
	error = QtWidgets.QMessageBox()
	error.setIcon( QtWidgets.QMessageBox.Critical )
	error.setText( message )
	error.setWindowTitle( title )
	error.setStandardButtons( QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No )
	return_value = error.exec_()
	return return_value == QtWidgets.QMessageBox.Yes


def Controller_Connection_Changed( label, identifier, is_connected ):
	if is_connected:
		label.setText( str(identifier) + " Connected" )
		label.setStyleSheet("QLabel { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255) }")
	else:
		label.setText( str(identifier) + " Not Connected" )
		label.setStyleSheet("QLabel { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255) }")


class IV_Measurement_Assistant_App(QWidget, Ui_MainWindow, Saveable_Session):

	measurementRequested_signal = QtCore.pyqtSignal(float, float, float, float)

	def __init__(self, parent=None, root_window=None):
		QtWidgets.QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		Saveable_Session.__init__( self, text_boxes = [(self.user_lineEdit, "user"),(self.descriptionFilePath_lineEdit, "pad_description_path"),(self.sampleName_lineEdit, "sample_name"),
					   (self.startVoltage_lineEdit, "start_v"),(self.endVoltage_lineEdit, "end_v"), (self.stepVoltage_lineEdit, "step_v"),
					   (self.startTemp_lineEdit, "start_T"),(self.endTemp_lineEdit, "end_T"), (self.stepTemp_lineEdit, "step_T")] )

		self.Init_Subsystems()
		self.Connect_Control_Logic()

		self.iv_controller_thread.start()
		self.temp_controller_thread.start()

		self.Restore_Session( resource_path( "session.ini" ) )

		self.current_data = None
		self.measurement = None

	def Init_Subsystems( self ):
		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ), config_error_popup=Popup_Yes_Or_No )
		self.config_window = TemperatureControllerSettingsWindow()

		# Run Connection to IV measurement system in another thread
		self.iv_controller = IV_Controller()
		self.iv_controller_thread = QtCore.QThread( self )
		self.iv_controller.moveToThread( self.iv_controller_thread )
		self.iv_controller_thread.started.connect( lambda : self.iv_controller.Initialize_Connection( "Keithley" ) )

		self.temp_controller = Temperature_Controller( resource_path( "configuration.ini" ) )
		self.temp_controller_thread = QtCore.QThread( self )
		self.temp_controller.moveToThread( self.temp_controller_thread )
		self.temp_controller_thread.started.connect( self.temp_controller.thread_start )



	def Open_Config_Window( self ):
		self.config_window.show()
		getattr(self.config_window, "raise")()
		self.config_window.activateWindow()

	def Connect_Control_Logic( self ):
		self.Stop_Measurement() # Initializes Measurement Sweep Button

		#self.establishComms_pushButton.clicked.connect( self.Establish_Comms )
		self.takeMeasurement_pushButton.clicked.connect( self.Take_Single_Measurement )
		self.outputToFile_pushButton.clicked.connect( self.Save_Data_To_File )
		self.saveToDatabase_pushButton.clicked.connect( self.Save_Data_To_Database )
		self.clearGraph_pushButton.clicked.connect( self.iv_Graph.clear_all_plots )

		self.measurementRequested_signal.connect( self.iv_controller.Voltage_Sweep )
		self.iv_controller.newSweepStarted_signal.connect( self.iv_Graph.new_plot )
		self.iv_controller.dataPointGotten_signal.connect( self.iv_Graph.add_new_data_point )
		self.iv_controller.sweepFinished_signal.connect( self.iv_Graph.plot_finished )

		self.selectDescriptionFile_pushButton.clicked.connect( self.Select_Device_File )

		# Temperature controller stuff
		self.config_window.Connect_Functions( self.temp_controller )
		self.openConfigurationWindow_pushButton.clicked.connect( self.Open_Config_Window )

		# Update labels on connection and disconnection to wifi devices
		self.iv_controller.ivControllerConnected_signal.connect( lambda : Controller_Connection_Changed( self.ivControllerConnected_label, "IV Controller", True ) )
		self.iv_controller.ivControllerDisconnected_signal.connect( lambda : Controller_Connection_Changed( self.ivControllerConnected_label, "IV Controller", False ) )
		self.temp_controller.Device_Connected.connect( lambda identifier, type_of_connection : Controller_Connection_Changed( self.tempControllerConnected_label, identifier, True ) )
		self.temp_controller.Device_Disconnected.connect( lambda : Controller_Connection_Changed( self.tempControllerConnected_label, "Temperature Controller", False ) )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemp_lineEdit.setText( '{:.2f}'.format( temperature ) ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.outputPower_lineEdit.setText( '{:.2f} %'.format( pid_output ) ) )



	def Select_Device_File( self ):
		fileName, _ = QFileDialog.getOpenFileName( self, "QFileDialog.getSaveFileName()", "", "CSV Files (*.csv);;All Files (*)" )
		if fileName == "": # User cancelled
			return
		try:
			config_info = Get_Device_Description_File( fileName )
		except Exception as e:
			Popup_Error( "Error", str(e) )
			return

		self.descriptionFilePath_lineEdit.setText( fileName )

	def Get_Measurement_Sweep_User_Input( self ):
		sample_name = self.sampleName_lineEdit.text()
		user = str( self.user_lineEdit.text() )
		if( sample_name == "" or user == "" ):
			raise ValueError( "Must enter a sample name and user" )

		try:
			temp_start, temp_end, temp_step = float(self.startTemp_lineEdit.text()), float(self.endTemp_lineEdit.text()), float(self.stepTemp_lineEdit.text())
			v_start, v_end, v_step = float(self.startVoltage_lineEdit.text()), float(self.endVoltage_lineEdit.text()), float(self.stepVoltage_lineEdit.text())
			time_interval = float( self.timeInterval_lineEdit.text() )
		except ValueError:
			raise ValueError( "Invalid arguement for temperature or voltage range" )

		device_config_data = Get_Device_Description_File( self.descriptionFilePath_lineEdit.text() )

		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )
		meta_data = dict( sample_name=sample_name, user=user, measurement_setup="LN2 Dewar" )

		return meta_data, (temp_start, temp_end, temp_step), (v_start, v_end, v_step, time_interval), device_config_data

	def Start_Measurement( self ):
		# Update button to reuse it for stopping measurement

		try:
			self.Save_Session( resource_path( "session.ini" ) )
			self.measurement = Measurement_Sweep_Runner( self, self.Stop_Measurement,
			                                             self.temp_controller, self.iv_controller,
			                                             *self.Get_Measurement_Sweep_User_Input(),
			                                             quit_early=self.takeMeasurementSweep_pushButton.clicked )
			print( "After" )
		except Exception as e:
			Popup_Error( "Error Starting Measurement", str(e) )
			return

		print( "self.takeMeasurementSweep_pushButton.clicked.disconnect()" )
		try: self.takeMeasurementSweep_pushButton.clicked.disconnect()
		except Exception: pass
		self.takeMeasurementSweep_pushButton.setText( "Stop Measurement" )
		self.takeMeasurementSweep_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")


	def Stop_Measurement( self ):
		try: self.takeMeasurementSweep_pushButton.clicked.disconnect()
		except Exception: pass
		self.takeMeasurementSweep_pushButton.setText( "Measurement Sweep" )
		self.takeMeasurementSweep_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.takeMeasurementSweep_pushButton.clicked.connect( self.Start_Measurement )

	def Set_Current_Data( self, x_data, y_data ):
		self.current_data = ( x_data, y_data )
		self.iv_controller.sweepFinished_signal.disconnect( self.Set_Current_Data )

	def Take_Single_Measurement( self ):
		input_start = float( self.startVoltage_lineEdit.text() )
		input_end = float( self.endVoltage_lineEdit.text() )
		input_step = float( self.stepVoltage_lineEdit.text() )
		time_interval = float( self.timeInterval_lineEdit.text() )
		self.iv_controller.sweepFinished_signal.connect( self.Set_Current_Data )
		self.measurementRequested_signal.emit( input_start, input_end, input_step, time_interval )

	def Save_Data_To_File( self ):
		if self.sampleName_lineEdit.text() == '':
			Popup_Error( "Error", "Must enter sample name" )
			return

		timestr = time.strftime("%Y%m%d-%H%M%S")
		sample_name = str( self.sampleName_lineEdit.text() )

		file_name = "IV Data_" + sample_name + "_" + timestr + ".csv"
		print( "Saving File: " + file_name )
		with open( file_name, 'w' ) as outfile:
			for x,y in zip( self.current_data[0], self.current_data[1] ):
				outfile.write( f'{x},{y}\n' )

	def Save_Data_To_Database( self ):
		if self.current_data == None:
			return

		sample_name = str( self.sampleName_lineEdit.text() )
		user = str( self.user_lineEdit.text() )
		if sample_name == ''  or user == '':
			Popup_Error( "Error", "Must enter sample name and user" )
			return

		meta_data_sql_entries = dict( sample_name=sample_name, user=user, temperature_in_k=None, measurement_setup="Microprobe",
					device_location=None, device_side_length_in_um=None, blackbody_temperature_in_c=None,
					bandpass_filter=None, aperture_radius_in_m=None )

		Commit_XY_Data_To_SQL( self.sql_type, self.sql_conn, xy_data_sql_table="iv_raw_data", xy_sql_labels=("voltage_v","current_a"),
						   x_data=self.current_data[0], y_data=self.current_data[1], metadata_sql_table="iv_measurements", **meta_data_sql_entries )

		print( "Data committed to database: " + sample_name  )


class Measurement_Sweep_Runner( QtCore.QObject ):
	Finished_signal = QtCore.pyqtSignal()
	def __init__( self, parent, finished, *args, **kargs ):
		QtCore.QObject.__init__(self)
		self.Finished_signal.connect( finished )
		self.args = args
		self.kargs = kargs
		# self.Run()
		self.thead_to_use = QtCore.QThread( parent=parent )
		self.moveToThread( self.thead_to_use )
		self.thead_to_use.started.connect( self.Run )
		# self.thead_to_use.finished.connect( self.thead_to_use.deleteLater )
		self.thead_to_use.start()

	def Run( self ):
		Measurement_Sweep( *self.args, **self.kargs )
		self.Finished_signal.emit()

def Measurement_Sweep( temp_controller, iv_controller,
                       meta_data, temperature_info, voltage_sweep_info, device_config_data,
                       quit_early ):
	sql_type, sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )

	run_devices  = Async_Iterator( device_config_data,
	                               temp_controller, lambda current_device, temp_controller=temp_controller : temp_controller.Set_Active_Pads( current_device.neg_pad, current_device.pos_pad ),
	                               temp_controller.Pads_Selected_Changed,
	                               quit_early )

	if temperature_info is None:
		turn_off_heater = [None]
		turn_heater_back_on = [None]
		run_temperatures = [None]
	else:
		turn_off_heater = Async_Iterator( [None],
		                                  temp_controller, lambda _ : temp_controller.Turn_Off(),
		                                  temp_controller.Heater_Output_Off,
		                                  quit_early )
		turn_heater_back_on = Async_Iterator( [None],
		                                      temp_controller, lambda _ : temp_controller.Turn_On(),
		                                      temp_controller.Temperature_Stable,
		                                      quit_early )
		temp_start, temp_end, temp_step = temperature_info
		run_temperatures = Async_Iterator( np.arange( temp_start, temp_end + temp_step / 2, temp_step ),
		                                   temp_controller, temp_controller.Set_Temp_And_Turn_On,
		                                   temp_controller.Temperature_Stable,
		                                   quit_early )

	v_start, v_end, v_step, time_interval = voltage_sweep_info
	get_results = Async_Iterator( [None],
	                              iv_controller, lambda *args, v_start=v_start, v_end=v_end, v_step=v_step, time_interval=time_interval :
	                                                    iv_controller.Voltage_Sweep( v_start, v_end, v_step, time_interval ),
	                              iv_controller.sweepFinished_signal,
	                              quit_early )

	# for temperature in run_temperatures:
	# 	for device, pads_info in run_devices:
	# 		for _ in turn_heater_back_on:
	for temperature, (device, pads_info), _ in ((x,y,z) for x in run_temperatures for y in run_devices for z in turn_heater_back_on ):
		meta_data.update( dict( temperature_in_k=temperature, device_location=device.location, device_side_length_in_um=device.side ) )
		(neg_pad, pos_pad), pads_are_reversed = pads_info
		print( f"Starting Measurement for {device.location} side length {device.side} at {temperature} K on pads {neg_pad} and {pos_pad}" )

		for _, xy_data in ((x,y) for x in turn_off_heater for y in get_results ):
			x_data, y_data = xy_data
			if pads_are_reversed:
				x_data = x_data[::-1]
				y_data = y_data[::-1]
			# Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="iv_raw_data", xy_sql_labels=("voltage_v","current_a"),
			# 					x_data=x_data, y_data=y_data, metadata_sql_table="iv_measurements", **meta_data )

	print( "this thread:", QtCore.QThread.currentThread() )
	print ( "temp_controller thread:", temp_controller.thread() )
	print( "Before Run_Async( temp_controller, temp_controller.Turn_Off ).Run()" )
	Run_Async( temp_controller, lambda : temp_controller.Turn_Off() ).Run()

	print( "Finished Measurment" )


if __name__ == '__main__':
	app = QApplication(sys.argv)
	ex = IV_Measurement_Assistant_App()
	ex.show()
	sys.exit(app.exec_())
