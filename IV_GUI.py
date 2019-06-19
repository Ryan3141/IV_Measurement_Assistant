if __name__ == "__main__": # This allows running this module by running this script
	import sys
	sys.path.insert(0, "..")

import sys
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QFileDialog
from PyQt5.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG
from PyQt5 import QtCore

import numpy as np
import configparser
import time

from MPL_Shared.Temperature_Controller import Temperature_Controller
from MPL_Shared.Temperature_Controller_Settings import TemperatureControllerSettingsWindow
from MPL_Shared.SQL_Controller import Commit_XY_Data_To_SQL, Connect_To_SQL
from MPL_Shared.IV_Measurement_Assistant import IV_Controller

from IV_Measurement_Assistant.Pad_Description_File import Get_Device_Description_File

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


class IV_Measurement_Assistant_App(QWidget, Ui_MainWindow):
	measurementRequested_signal = QtCore.pyqtSignal(float, float, float)

	def __init__(self, parent=None, root_window=None):
		QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		self.current_data = None
		self.measurement_actively_running = False

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
		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )
		self.config_window = TemperatureControllerSettingsWindow()

		self.temp_controller = Temperature_Controller( configuration_file, parent=self )

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

		self.selectDescriptionFile_pushButton.clicked.connect( self.Select_Device_File )
		self.config_window.Connect_Functions( self.temp_controller )
		self.openConfigurationWindow_pushButton.clicked.connect( lambda : self.config_window.show() )
		self.takeMeasurementSweep_pushButton.clicked.connect( self.Start_Measurement_Sweep )

		# Update labels on connection and disconnection to wifi devices
		self.temp_controller.Device_Connected.connect( self.Temp_Controller_Connected )
		self.temp_controller.Device_Disconnected.connect( self.Temp_Controller_Disconnected )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemp_lineEdit.setText( '{:.2f}'.format( temperature ) ) )


	def Temp_Controller_Connected( self, identifier, type_of_connection ):
		self.tempControllerConnected_label.setText( str(identifier) + " Connected" )
		self.tempControllerConnected_label.setStyleSheet("QLabel { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255) }")

	def Temp_Controller_Disconnected( self ):
		self.tempControllerConnected_label.setText( "Temperature Controller Not Connected" )
		self.tempControllerConnected_label.setStyleSheet("QLabel { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255) }")


	def Set_Current_Data( self, x_data, y_data ):
		self.current_data = ( x_data, y_data )
		self.iv_Graph.plot_finished( x_data, y_data )

	def ivConnectionStateChanged( self, connected_or_disconnected ):
		if connected_or_disconnected:
			pass

	def Establish_Comms( self ):
		self.iv_communications = IV_Measurement_Assistant.Initialize_Connection()

	def Take_Measurement( self ):
		input_start = float( self.startVoltage_lineEdit.text() )
		input_end = float( self.endVoltage_lineEdit.text() )
		input_step = float( self.stepVoltage_lineEdit.text() )

		try: self.iv_controller.sweepFinished_signal.disconnect() 
		except Exception: pass
		self.iv_controller.sweepFinished_signal.connect( self.Set_Current_Data )
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

		file_name = "IV Data_" + sample_name + "_" + timestr + ".csv"
		print( "Saving File: " + file_name )
		with open( file_name, 'w' ) as outfile:
			outfile.write( ','.join([str(x) for x in self.current_data[0]]) + '\n' )
			outfile.write( ','.join([str(x) for x in self.current_data[1]]) + '\n' )

	def Save_Data_To_Database( self ):
		if self.current_data == None:
			return

		sample_name = str( self.sampleName_lineEdit.text() )
		user = str( self.user_lineEdit.text() )
		if sample_name == ''  or user == '':
			Popup_Error( "Error", "Must enter sample name and user" )
			return

		meta_data_sql_entries = dict( sample_name=sample_name, user=user, temperature_in_k=None, measurement_setup="Microprobe",
					location=None, device_size=None, blackbody_temperature_in_c=None,
					bandpass_filter=None, aperture_radius_in_m=None )

		Commit_XY_Data_To_SQL( self.sql_type, self.sql_conn, xy_data_sql_table="iv_raw_data", xy_sql_labels=("voltage_v","current_a"),
						   x_data=self.current_data[0], y_data=self.current_data[1], metadata_sql_table="iv_measurements", **meta_data_sql_entries )

		print( "Data committed to database: " + sample_name + "_" + str(location_x) + "_" + str(location_y) )

	def Select_Device_File( self ):
		fileName, _ = QFileDialog.getOpenFileName( self, "QFileDialog.getSaveFileName()", "", "CSV Files (*.csv);;All Files (*)" )
		config_info = Get_Device_Description_File( fileName )
		if config_info is None:
			Popup_Error( "Error", "Invalid device file given" )
			return

		self.descriptionFilePath_lineEdit.setText( fileName )


	def Start_Measurement_Sweep( self ):
		try:
			temp_start, temp_end, temp_step = float(self.startTemp_lineEdit.text()), float(self.endTemp_lineEdit.text()), float(self.stepTemp_lineEdit.text())
			v_start, v_end, v_step = float(self.startVoltage_lineEdit.text()), float(self.endVoltage_lineEdit.text()), float(self.stepVoltage_lineEdit.text())
		except:
			Popup_Error( "Error", "Invalid arguement for temperature or voltage range" )
			return

		device_config_data = Get_Device_Description_File( self.descriptionFilePath_lineEdit.text() )
		if device_config_data is None:
			Popup_Error( "Error", "Invalid device file given" )
			return

		temperatures_to_measure = np.arange( temp_start, temp_end + temp_step, temp_step )
		sample_name = self.sampleName_lineEdit.text()
		user = str( self.user_lineEdit.text() )
		if( sample_name == "" or user == "" ):
			Popup_Error( "Error", "Must enter a sample name and user" )
			return

		self.takeMeasurementSweep_pushButton.clicked.disconnect()
		#self.takeMeasurementSweep_pushButton.setText( "Stop Measurement" )
		self.takeMeasurementSweep_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.takeMeasurementSweep_pushButton.clicked.connect( self.Stop_Measurment_Sweep )

		self.Run_Measurment_Loop( sample_name=sample_name, user=user, device_config_data=device_config_data, temperatures_to_measure=temperatures_to_measure, v_start=v_start, v_end=v_end, v_step=v_step )

	def Stop_Measurment_Sweep( self ):
		self.measurement_actively_running = False
		if self.temp_controller is not None:
			self.temp_controller.Turn_Off()

		try: self.run_pushButton.clicked.disconnect() 
		except Exception: pass
		
		#self.takeMeasurementSweep_pushButton.setText( "Run Sweep" )
		self.takeMeasurementSweep_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.takeMeasurementSweep_pushButton.clicked.connect( self.Start_Measurement_Sweep )

	def Wait_For_Stable_Temp( self, temperature ):
		self.temp_controller.Set_Temperature_In_K( temperature )
		self.temp_controller.Turn_On()

		while( not self.temp_controller.Temperature_Is_Stable() ):
			QtCore.QCoreApplication.processEvents()
			if not self.measurement_actively_running:
				print( "Quitting measurment early" )
				return False
		print( "Temperature stable around: " + str(temperature) + '\n' )
		return True

	def Pads_Ready( self, pads, is_reversed ):
		self.waiting_on_pads = False
		self.pads_are_reversed = is_reversed

	def Wait_For_Pads_Set( self, pad1, pad2 ):
		self.waiting_on_pads = True
		temp_connection = self.temp_controller.Pads_Selected_Changed.connect( self.Pads_Ready )
		self.temp_controller.Set_Active_Pads( int(pad1), int(pad2) )
		while( self.waiting_on_pads ):
			QtCore.QCoreApplication.processEvents()
			if not self.measurement_actively_running:
				print( "Quitting measurment early" )
				self.temp_controller.Pads_Selected_Changed.disconnect( temp_connection )
				return False
		self.temp_controller.Pads_Selected_Changed.disconnect( temp_connection )
		return True

	def Run_Measurment_Loop( self, sample_name, user, device_config_data, temperatures_to_measure, v_start, v_end, v_step ):
		expected_data = ["Negative Pad","Positive Pad","Device Area (um^2)","Device Perimeter (um)"]
		for temperature in temperatures_to_measure:
			for device_index in range( len(device_config_data["Negative Pad"]) ):

				self.measurement_actively_running = True
				should_continue_measurement = self.Wait_For_Pads_Set( device_config_data["Negative Pad"][device_index], device_config_data["Positive Pad"][device_index] )
				if not should_continue_measurement:
					return
				should_continue_measurement = self.Wait_For_Stable_Temp( temperature )
				if not should_continue_measurement:
					return

				print( "Starting Measurement\n" )
				meta_data = dict( sample_name=sample_name, user=user, temperature_in_k=temperature,
					 device_area_in_um2=device_config_data["Device Area (um^2)"][device_index], device_location=device_config_data["Device Location"][device_index],
					 device_perimeter_in_um=device_config_data["Device Perimeter (um)"][device_index], measurement_setup="LN2 Dewar" )
				try: self.iv_controller.sweepFinished_signal.disconnect() 
				except Exception: pass
				self.iv_controller.sweepFinished_signal.connect( self.Set_Current_Data )
				self.iv_controller.sweepFinished_signal.connect( lambda x_data, y_data :
													self.Sweep_Part_Finished( x_data, y_data, sql_type=self.sql_type, sql_conn=self.sql_conn, meta_data=meta_data ) )
				self.measurementRequested_signal.emit( v_start, v_end, v_step )

				while( self.measurement_actively_running == True ):
					QtCore.QCoreApplication.processEvents()

		self.Stop_Measurment_Sweep()
		print( "Finished Measurment" )

	def Sweep_Part_Finished( self, x_data, y_data, sql_type, sql_conn, meta_data ):
		if self.pads_are_reversed:
			x_data = reversed( x_data )
			y_data = reversed( y_data )
		self.measurement_actively_running = False
		Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="iv_raw_data", xy_sql_labels=("voltage_v","current_a"),
							x_data=x_data, y_data=y_data, metadata_sql_table="iv_measurements", **meta_data )

if __name__ == '__main__':
	app = QApplication(sys.argv)
	ex = IV_Measurement_Assistant_App()
	ex.show()
	sys.exit(app.exec_())