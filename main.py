#!/usr/bin/env python
import httplib
import json
import logging
import time
import sys

# measure the elapsed time
MEASURE_ELAPSED_TIME = True
SHOW_DEBUG_LOG = False
FUNDA_DEFAULT_TOP = 10

# environment initialization
reload(sys)
sys.setdefaultencoding('utf-8')

if SHOW_DEBUG_LOG : 
	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	handler = logging.StreamHandler(sys.stdout)
	handler.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	handler.setFormatter(formatter)
	logger.addHandler(handler)

FUNDA_API_HOSTNAME = 'partnerapi.funda.nl'
FUNDA_API_KEY = '005e7c1d6f6c4f9bacac16760286e3cd'
FUNDA_API_PATH = 'feeds/Aanbod.svc'

def parseBoolean(s):
	'''
	helper method to parse the boolean value
	'''
	if s == None or len(s) == 0 :
		return None
	if s[0].upper() == 'Y' :
		return True
	elif s[0].upper() == 'N' :
		return False
	return None

class FundaMain:
	'''
	the main class
	'''
	def __init__(self, config = None):
		if config :
			self.hostname = config['hostname']
			self.key = config['key']
			self.path = config['path']
		else:
			self.hostname = FUNDA_API_HOSTNAME
			self.key = FUNDA_API_KEY
			self.path = FUNDA_API_PATH
		
		self.makelaars = {}
		self.key_path = '/' + self.path + '/' + self.key

	def add(self, result):
		'''
		Read the json result, and then, add a new entry with key = makelaarNaam, and value = 1, 
		or increment the value of an existing makelaar
		
		Remark: There are some makelaars' have extactly same name but different MakelaarId, 
				therefore, the key used is 'MakelaarNaam' rather than 'MakelaarId'
		
		Remark: if there are more than one thread used, checking the existence and adding new entry, 
				and also increment the Count should be thread-safe
		
		@param result the json result retrieved from the Funda API
		'''
		
		for makelaarNaam in list(map(lambda makelaar : makelaar['MakelaarNaam'], result['Objects'])) :
			if makelaarNaam in self.makelaars :
				self.makelaars[makelaarNaam] += 1
			else :
				self.makelaars[makelaarNaam] = 1
	
	def topMakelaars(self, top):
		'''
		Find the top makelaars, 
		if from the top-th makelaar to (top+k)-th makelaar, where k > 1, have the same 
		number of houses for sale, then all the makelaars are included in the result
		
		@param top The top N-th makelaars
		
		@return A list of top N-th makelaars
		'''
		if len(self.makelaars) == 0 :
			return []
		
		# sort the list
		results = sorted(self.makelaars, key=lambda makelaar : int(self.makelaars[makelaar]), reverse=True)
		
		if top :
			# shows the tied makelaars
			while results[top-1] == results[top] :
				top += 1
			
			results = enumerate(results[:top])
		
		return results

	def start(self, filters, top = FUNDA_DEFAULT_TOP, display = True):
		'''
		The main entrance of the program, general steps:
		1. initialize the filters, parameters and http connection
		2. loop all the pages, and add the 
		3. summarize and display the results
		
		@param filters The filters used for Funda API
		
		@param top The top N-th makelaars
		'''
		print 'Session start'
		
		headers = {
			'Content-Type':'text/plain; charset=utf-8',
			'Accept' : 'application/json'
		}
		
		totalPages = -1
		filters['page'] = 1
		filters['pagesize'] = 25
		connection = httplib.HTTPConnection(self.hostname)
		
		sucess = True
		while sucess and (int(filters['page']) < totalPages or totalPages < 0) :
			
			parameters = '&'.join('%s=%s' % (key,value) for key, value in filters.iteritems())
			
			logging.debug('Starting:: %s' % parameters)
			
			# Remark: The http requests could be asynchronous
			try:
				connection.request('GET', self.key_path + '/?' + parameters, None, headers)
				
				logging.debug('waiting for the response....\r')
				response = connection.getresponse()
				status = response.status
				
				if status == 200 :
				
					logging.debug('reading response.... (%s)\r' % status)
					data = response.read()
					logging.debug('reading response.... (%s) ... finished.\r' % status)
					result = json.loads(data)
					if totalPages < 0 :
						# the first request, initialize multiple async requests 
						# related based on the total number of requests (totalPages) required
						totalPages = result['Paging']['AantalPaginas']
						totalItems = result['TotaalAantalObjecten']
						print 'There are %s results in %s page%s.' % (totalItems, totalPages, 's' if totalPages>1 else '')
					
					self.add(result)
					
					filters['page'] = int(filters['page']) + 1
					
				else :
					logging.error('Failed!! Status: %s' % status)
					logging.error('Failed! Filters: %s' % data)
					totalPages = 0
					sucess = False
			
			except HTTPException as ex:
				totalPages = 0
				sucess = False
				print ex
			
			finally :
				connection.close()
		
		results = None
		connection = None
		if sucess : 
			results = self.topMakelaars(top)
			if display:
				print ''
				print '--- Top %s makelaars in "%s" ---' % (top, filters['zo'])
				print ''
				
				for index, makelaar in results:
					print '%2s %4s %s' % (index+1, self.makelaars[makelaar], makelaar)
				
				print ''
				print '--- Top %s makelaars in "%s" ---' % (top, filters['zo'])
		
		print 'Session end'
		
		return list(results) if results else None

'''
Program starts from here
1. get and validate the input
2. start the process
3. exit or repeat
'''
print ''
print 'This program can find out the top N-th makelaars via the funda API'
print ''
print 'Program start'

main = None
again = True
city = ''

while again:
	validInput = False
	hasGarden = None
	
	while not validInput :
		
		if len(city) > 0 :
			cityInput = raw_input('Enter a city name (%s): ' % city)
		else :
			cityInput = raw_input('Enter a city name: ')
		
		if len(cityInput) > 0 :
			city = cityInput
		
		hasGarden = raw_input('Only with garden? (y/n): ')
		hasGarden = parseBoolean(hasGarden)
		
		top = FUNDA_DEFAULT_TOP
		topInput = raw_input('Top n-th makelaars? (number, default 10): ')
		
		try : 
			if len(topInput) > 0 and int(topInput) is not None :
				top = int(topInput)
			
			if len(city) > 0 and hasGarden != None : 
				validInput = True
			else :
				raise Error
		except :
			print 'Invalid input!'
			print ''
			
	zo = '/' + city + '/'
	if hasGarden :
		zo += 'tuin/'

	if main == None :
		main = FundaMain()
	
	filters = {'type':'koop', 'zo': zo }
	
	if MEASURE_ELAPSED_TIME :
		start = time.time()
		main.start(filters, top)
		end = time.time()
		print 'total execution time %.5g seconds.' % (end - start)
	else :
		main.start(filters, top)
	
	again = None
	while again == None :
		again = raw_input('Try again? (y/n): ')
		again = parseBoolean(again)
	
	print ''

main = None
print 'Program end'
