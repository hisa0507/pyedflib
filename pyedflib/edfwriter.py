# -*- coding: utf-8 -*-
# Copyright (c) 2015, Holger Nahrstaedt
# Copyright (c) 2011, 2015, Chris Lee-Messer
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import division, print_function, absolute_import

import numpy as np
import sys
from datetime import datetime, date
from ._pyedflib import FILETYPE_EDFPLUS, FILETYPE_BDFPLUS
from ._pyedflib import open_file_writeonly, set_physical_maximum, set_patient_additional, set_digital_maximum
from ._pyedflib import set_birthdate, set_digital_minimum, set_technician, set_recording_additional, set_patientname
from ._pyedflib import set_patientcode, set_equipment, set_admincode, set_gender, set_datarecord_duration
from ._pyedflib import set_startdatetime, set_samplefrequency, set_physical_minimum, set_label, set_physical_dimension
from ._pyedflib import set_transducer, set_prefilter, write_physical_samples, close_file, write_annotation_latin1, write_annotation_utf8


__all__ = ['EdfWriter']


if sys.version_info < (3,):
    import codecs

    def u(x):
        return codecs.unicode_escape_decode(x)[0]

    def du(x):
        if isinstance(x, unicode):
            return x.encode("utf-8")
        else:
            return x
else:
    def u(x):
        return x

    def du(x):
        return x.encode("utf-8")


class ChannelDoesNotExist(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class WrongInputSize(Exception):
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class EdfWriter(object):
    def __exit__(self, exc_type, exc_val, ex_tb):
        self.close()  # cleanup the file

    def __init__(self, file_name, n_channels,
                 file_type=FILETYPE_EDFPLUS):
        """Initialises an EDF file at @file_name.
        @file_type is one of
            edflib.FILETYPE_EDF
            edflib.FILETYPE_EDFPLUS
            edflib.FILETYPE_BDF
            edflib.FILETYPE_BDFPLUS
        @n_channels is the number of channels without the annotation channel
        (only FILETYPE_EDFPLUS or FILETYPE_BDFPLUS)

        @channel_info should be a
        list of dicts, one for each channel in the data. Each dict needs
        these values:

            'label' : channel label (string, <= 16 characters, must be unique)
            'dimension' : physical dimension (e.g., mV) (string, <= 8 characters)
            'sample_rate' : sample frequency in hertz (int)
            'physical_max' : maximum physical value (float)
            'physical_min' : minimum physical value (float)
            'digital_max' : maximum digital value (int, -2**15 <= x < 2**15)
            'digital_min' : minimum digital value (int, -2**15 <= x < 2**15)
        """
        self.path = file_name
        self.file_type = file_type
        self.patient_name = ''
        self.patient_code = ''
        self.technician = ''
        self.equipment = ''
        self.recording_additional = ''
        self.patient_additional = ''
        self.admincode = ''
        self.gender = 0
        self.recording_start_time = datetime.now()
        self.birthdate = date(1900, 1, 1)
        self.duration = 1
        self.n_channels = n_channels
        self.channels = []
        self.sample_buffer = []
        for i in np.arange(self.n_channels):
            if self.file_type == FILETYPE_EDFPLUS or self.file_type == FILETYPE_BDFPLUS:
                self.channels.append({'label': 'test_label', 'dimension': 'mV', 'sample_rate': 100,
                                      'physical_max': 1.0, 'physical_min': -1.0,
                                      'digital_max': 8388607,'digital_min': -8388608,
                                      'prefilter': 'pre1', 'transducer': 'trans1'})
            else:
                self.channels.append({'label': 'test_label', 'dimension': 'mV', 'sample_rate': 100,
                                      'physical_max': 1.0, 'physical_min': -1.0,
                                      'digital_max': 32767, 'digital_min': -32768,
                                      'prefilter': 'pre1', 'transducer': 'trans1'})

                self.sample_buffer.append([])
        self.handle = open_file_writeonly(self.path, self.file_type, self.n_channels)

    def update_header(self):
        """
        Updates header to edffile struct
        """
        set_technician(self.handle, u(self.technician).encode('UTF-8'))
        set_recording_additional(self.handle, u(self.recording_additional).encode('UTF-8'))
        set_patientname(self.handle, u(self.patient_name).encode('UTF-8'))
        set_patientcode(self.handle, u(self.patient_code).encode('UTF-8'))
        set_patient_additional(self.handle, u(self.patient_additional).encode('UTF-8'))
        set_equipment(self.handle, u(self.equipment).encode('UTF-8'))
        set_admincode(self.handle, u(self.admincode).encode('UTF-8'))
        if isinstance(self.gender, int):
            set_gender(self.handle, self.gender)
        elif self.gender == "Male":
            set_gender(self.handle, 0)
        elif self.gender == "Female":
            set_gender(self.handle, 1)

        set_datarecord_duration(self.handle, self.duration)
        set_startdatetime(self.handle, self.recording_start_time.year, self.recording_start_time.month,
                          self.recording_start_time.day, self.recording_start_time.hour,
                          self.recording_start_time.minute, self.recording_start_time.second)
        if isinstance(self.birthdate, str):
            if self.birthdate == '':
                birthday = date(1900, 1, 1)
            else:
                birthday = datetime.strptime(self.birthdate, '%d %b %Y').date()
            set_birthdate(self.handle, birthday.year, birthday.month, birthday.day)
        else:
            set_birthdate(self.handle, self.birthdate.year, self.birthdate.month, self.birthdate.day)
        for i in np.arange(self.n_channels):
            set_samplefrequency(self.handle, i, self.channels[i]['sample_rate'])
            set_physical_maximum(self.handle, i, self.channels[i]['physical_max'])
            set_physical_minimum(self.handle, i, self.channels[i]['physical_min'])
            set_digital_maximum(self.handle, i, self.channels[i]['digital_max'])
            set_digital_minimum(self.handle, i, self.channels[i]['digital_min'])
            set_label(self.handle, i, u(self.channels[i]['label']).encode('UTF-8'))
            set_physical_dimension(self.handle, i, u(self.channels[i]['dimension']).encode('UTF-8'))
            set_transducer(self.handle, i, u(self.channels[i]['transducer']).encode('UTF-8'))
            set_prefilter(self.handle, i, u(self.channels[i]['prefilter']).encode('UTF-8'))

    def setHeader(self, fileHeader):
        """
        Sets the file header
        """
        self.technician = fileHeader["technician"]
        self.recording_additional = fileHeader["recording_additional"]
        self.patient_name = fileHeader["patientname"]
        self.patient_additional = fileHeader["patient_additional"]
        self.patient_code = fileHeader["patientcode"]
        self.equipment = fileHeader["equipment"]
        self.admincode = fileHeader["admincode"]
        self.gender = fileHeader["gender"]
        self.recording_start_time = fileHeader["startdate"]
        self.birthdate = fileHeader["birthdate"]
        self.update_header()

    def setSignalHeader(self, edfsignal, channel_info):
        """
        Sets the parameter for signal edfsignal.

        @channel_info should be a dict with
        these values:

            'label' : channel label (string, <= 16 characters, must be unique)
            'dimension' : physical dimension (e.g., mV) (string, <= 8 characters)
            'sample_rate' : sample frequency in hertz (int)
            'physical_max' : maximum physical value (float)
            'physical_min' : minimum physical value (float)
            'digital_max' : maximum digital value (int, -2**15 <= x < 2**15)
            'digital_min' : minimum digital value (int, -2**15 <= x < 2**15)
        """
        if edfsignal < 0 or edfsignal > self.n_channels:
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal] = channel_info
        self.update_header()

    def setSignalHeaders(self, signalHeaders):
        """
        Sets the parameter for all signals

        Parameters
        ----------
        signalHeaders : array_like
            containing dict with
                'label' : str
                          channel label (string, <= 16 characters, must be unique)
                'dimension' : str
                          physical dimension (e.g., mV) (string, <= 8 characters)
                'sample_rate' : int
                          sample frequency in hertz
                'physical_max' : float
                          maximum physical value
                'physical_min' : float
                         minimum physical value
                'digital_max' : int
                         maximum digital value (-2**15 <= x < 2**15)
                'digital_min' : int
                         minimum digital value (-2**15 <= x < 2**15)
        """
        for edfsignal in np.arange(self.n_channels):
            self.channels[edfsignal] = signalHeaders[edfsignal]
        self.update_header()

    def setTechnician(self, technician):
        """
        Sets the technicians name to @technician.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.technician = technician
        self.update_header()

    def setRecordingAdditional(self, recording_additional):
        """
        Sets the additional recordinginfo

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.recording_additional = recording_additional
        self.update_header()

    def setPatientName(self, patient_name):
        """
        Sets the patientname to @patient_name.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.patient_name = patient_name
        self.update_header()

    def setPatientCode(self, patient_code):
        """
        Sets the patientcode to @patient_code.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.patient_code = patient_code
        self.update_header()

    def setPatientAdditional(self, patient_additional):
        """
        Sets the additional patientinfo to @patient_additional.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.technician = patient_additional
        self.update_header()

    def setEquipment(self, equipment):
        """
        Sets the name of the @param equipment used during the aquisition.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.

        Parameters
        ----------
        equipment : str
                    Describes the measurement equpipment

        """
        self.equipment = equipment
        self.update_header()

    def setAdmincode(self, admincode):
        """
        Sets the admincode.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.

        Parameters
        ----------
        admincode : str
                   admincode which is written into the header

        """
        self.admincode = admincode
        self.update_header()

    def setGender(self, gender):
        """
        Sets the gender.

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.

        Parameters
        ----------
        gender : int
                 1 is male, 0 is female
        """
        self.gender = gender
        self.update_header()

    def setDatarecordDuration(self, duration):
        """
        Sets the datarecord duration. The default value is 1 second.
        This function is optional, normally you don't need to change
        the default value. The datarecord duration must be in the range 0.05 to 20.0 seconds.
        Returns 0 on success, otherwise -1.

        :param duration: float

        This function is NOT REQUIRED but can be called after opening a file in writemode and
        before the first sample write action. This function can be used when you want
        to use a samplerate which is not an integer. For example, if you want to use
        a samplerate of 0.5 Hz, set the samplefrequency to 5 Hz and
        the datarecord duration to 10 seconds. Do not use this function,
        except when absolutely necessary!
        """
        self.duration = duration
        self.update_header()

    def setStartdatetime(self, recording_start_time):
        """
        Sets the recording start Time
        :param recording_start_time:
        """
        self.recording_start_time = recording_start_time
        self.update_header()

    def setBirthdate(self, birthdate):
        """
        Sets the birthdate.

        :param birthdate:

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        self.birthdate = birthdate
        self.update_header()

    def setSamplefrequency(self, edfsignal, samplefrequency):
        """
        Sets the samplefrequency of signal edfsignal.

        This function is required for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if edfsignal < 0 or edfsignal > self.n_channels:
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['sample_rate'] = samplefrequency
        self.update_header()

    def setPhysicalMaximum(self, edfsignal, physical_maximum):
        """
        Sets the physical_maximum of signal edfsignal.

        :param edfsignal: int
        :param physical_maximum: float

        This function is required for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if edfsignal < 0 or edfsignal > self.n_channels:
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['physical_max'] = physical_maximum
        self.update_header()

    def setPhysicalMinimum(self, edfsignal, physical_minimum):
        """
        Sets the physical_minimum of signal edfsignal.

        :param edfsignal: int
        :param physical_minimum: float

        This function is required for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if (edfsignal < 0 or edfsignal > self.n_channels):
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['physical_min'] = physical_minimum
        self.update_header()

    def setDigitalMaximum(self, edfsignal, digital_maximum):
        """
        Sets the samplefrequency of signal edfsignal.
        Usually, the value 32767 is used for EDF+ and 8388607 for BDF+.

        :param edfsignal: int
        :param digital_maximum: int

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        if (edfsignal < 0 or edfsignal > self.n_channels):
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['digital_max'] = digital_maximum
        self.update_header()

    def setDigitalMinimum(self, edfsignal, digital_minimum):
        """
        Sets the minimum digital value of signal edfsignal.
        Usually, the value -32768 is used for EDF+ and -8388608 for BDF+. Usually this will be (-(digital_maximum + 1)).

        :param edfsignal: int
        :param digital_minimum: int

        This function is optional and can be called only after opening a file in writemode and before the first sample write action.
        """
        if (edfsignal < 0 or edfsignal > self.n_channels):
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['digital_min'] = digital_minimum
        self.update_header()

    def setLabel(self, edfsignal, label):
        """
        Sets the label (name) of signal edfsignal ("FP1", "SaO2", etc.).

        :param edfsignal: int
        :param label: str

        This function is recommended for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if (edfsignal < 0 or edfsignal > self.n_channels):
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['label'] = label
        self.update_header()

    def setPhysicalDimension(self, edfsignal, physical_dimension):
        """
        Sets the physical dimension of signal edfsignal ("uV", "BPM", "mA", "Degr.", etc.)

        :param edfsignal: int
        :param physical_dimension: str

        This function is recommended for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if edfsignal < 0 or edfsignal > self.n_channels:
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['dimension'] = physical_dimension
        self.update_header()

    def setTransducer(self, edfsignal, transducer):
        """
        Sets the transducer of signal edfsignal

        :param edfsignal: int
        :param transducer: str

        This function is optional for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if (edfsignal < 0 or edfsignal > self.n_channels):
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['transducer'] = transducer
        self.update_header()

    def setPrefilter(self, edfsignal, prefilter):
        """
        Sets the prefilter of signal edfsignal ("HP:0.1Hz", "LP:75Hz N:50Hz", etc.)

        :param edfsignal: int
        :param prefilter: str

        This function is optional for every signal and can be called only after opening a file in writemode and before the first sample write action.
        """
        if edfsignal < 0 or edfsignal > self.n_channels:
            raise ChannelDoesNotExist(edfsignal)
        self.channels[edfsignal]['prefilter'] = prefilter
        self.update_header()

    def writePhysicalSamples(self, data):
        """
        Writes n physical samples (uV, mA, Ohm) belonging to one signal where n
        is the samplefrequency of the signal.

        @data_vec belonging to one signal. The size must be the samplefrequency of the signal.


        Writes n physical samples (uV, mA, Ohm) from data_vec belonging to one signal where n
        is the samplefrequency of the signal. The physical samples will be converted to digital
        samples using the values of physical maximum, physical minimum, digital maximum and digital
        minimum. The number of samples written is equal to the samplefrequency of the signal.
        Call this function for every signal in the file. The order is important! When there are 4
        signals in the file, the order of calling this function must be: signal 0, signal 1, signal 2,
        signal 3, signal 0, signal 1, signal 2, etc.

        All parameters must be already written into the bdf/edf-file.
        """
        return write_physical_samples(self.handle, data)

    def writeSamples(self, data_list):
        """
        Writes physical samples (uV, mA, Ohm) from data belonging to all signals
        The physical samples will be converted to digital samples using the values
        of physical maximum, physical minimum, digital maximum and digital minimum.
        if the samplefrequency of all signals are equal, then the data could be
        saved into a matrix with the size (N,signals) If the samplefrequency
        is different, then sample_freq is a vector containing all the different
        samplefrequencys. The data is saved as list. Each list entry contains
        a vector with the data of one signal.

        All parameters must be already written into the bdf/edf-file.
        """

        if (len(data_list) != len(self.channels)):
            raise WrongInputSize(len(data_list))

        ind = []
        notAtEnd = True
        for i in np.arange(len(data_list)):
            ind.append(0)

        for i in np.arange(len(data_list)):
            if (np.size(data_list[i]) < ind[i] + self.channels[i]['sample_rate']):
                notAtEnd = False

        while notAtEnd:
            for i in np.arange(len(data_list)):
                self.writePhysicalSamples(data_list[i].flatten()[ind[i]:ind[i]+self.channels[i]['sample_rate']])
                ind[i] += self.channels[i]['sample_rate']

            for i in np.arange(len(data_list)):
                if (np.size(data_list[i]) < ind[i] + self.channels[i]['sample_rate']):
                    notAtEnd = False

        for i in np.arange(len(data_list)):
            lastSamples = np.zeros(self.channels[i]['sample_rate'])
            lastSampleInd = np.max(data_list[i].shape) - ind[i]
            if lastSampleInd > 0:
                lastSamples[:lastSampleInd] = data_list[i].flatten()[-lastSampleInd:]
                self.writePhysicalSamples(lastSamples)

    def writeAnnotation(self, onset_in_seconds, duration_in_seconds, description, str_format='utf-8'):
        """
        Writes an annotation/event to the file
        """
        if str_format == 'utf-8':
            if duration_in_seconds >= 0:
                return write_annotation_utf8(self.handle, np.round(onset_in_seconds*10000).astype(int), np.round(duration_in_seconds*10000).astype(int), du(description))
            else:
                return write_annotation_utf8(self.handle, np.round(onset_in_seconds*10000).astype(int), -1, du(description))
        else:
            if duration_in_seconds >= 0:
                return write_annotation_latin1(self.handle, np.round(onset_in_seconds*10000).astype(int), np.round(duration_in_seconds*10000).astype(int), u(description).encode('latin1'))
            else:
                return write_annotation_latin1(self.handle, np.round(onset_in_seconds*10000).astype(int), -1, u(description).encode('latin1'))

    def close(self):
        """
        Closes the file.
        """
        close_file(self.handle)
