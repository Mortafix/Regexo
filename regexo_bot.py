import logging
import os
from telegram import ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, PicklePersistence
from emoji import emojize
from datetime import date
from re import match,search,sub
from re import error as ReError
import redis
from math import floor
from random import choice


# Enable logging and port
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
logger = logging.getLogger(__name__)
PORT = int(os.environ.get('PORT', 5000))
# Config variables
TOKEN = os.environ.get("TOKEN")
ADD_TEST,NEW_TEST,ADD_DESCRIPTION,DATE_CHOOSE,LIST_C,LIST_M,PLAY,PLAY_DISPACTHER,ADD_DIFFICULTY = range(9)
# Redis Setup
TERMINAL = True if os.environ.get('TERM_PROGRAM') else False
REGEX = redis.Redis(host='localhost', port=6379, db=0) if TERMINAL else redis.from_url(os.environ.get("REDIS_URL"))

#--------------------------------- Functions ------------------------------------------

# Base function ---------------------------

def are_you_admin(telegram_id):
	return telegram_id in [18528224,]

def debug_redis(update,context):
	telegram_id = update.message.chat.id
	if are_you_admin(telegram_id):
		msg = '\n\n'.join(['{}\n{}'.format(k.decode(),'\n'.join(['{}: {}'.format(key.decode(),REGEX.hget(k,key).decode().replace('\n',' > ')) for key in sorted(REGEX.hkeys(k))])) for k in sorted(REGEX.keys())])
		with open('debug.txt','w') as f: f.write(msg)
		update.message.reply_document(document=open('debug.txt', 'rb'))

def date_to_key(date_key=None):
	date_key =  date.today() if not date_key else date.fromisoformat('-'.join(date_key.split('-')[::-1]))
	return int('{:04d}{:02d}{:02d}'.format(date_key.year,date_key.month,date_key.day))

def key_to_date(key):
	return '{2}.{1}.{0}'.format(key[0:4],key[4:6],key[6:8])

def em(emoji_string):
	return emojize(':'+emoji_string+':',use_aliases=True)

def challenge_exists(key):
	return key in REGEX

def are_you_alive(telegram_id,user):
	if 'u{}'.format(telegram_id) not in get_users():
		db_name = user.username if user.username else user.first_name
		REGEX.hset('u{}'.format(telegram_id),'username',db_name)
		REGEX.hset('u{}'.format(telegram_id),'show',1)

# Playing function ---------------------------

def print_challenge(regex_list=None,index=None,key=None,number=None,usr_id=None):
	if regex_list: key = regex_list[index]
	descr = REGEX.hget(key,'descr').decode()
	difficulty = REGEX.hget(key,'difficulty').decode()
	test = [REGEX.hget(key,k).decode().split('\n') for k in sorted(REGEX.hkeys(key)) if search(r'test',str(k))]
	return '{} *{}*\n{}\n{}\n\n{}{}'.format(em('date'),key_to_date(str(key)),print_difficulty(difficulty),descr,print_tests(test,number),print_player(usr_id,key))

def print_player(user,key):
	player_play = REGEX.hget('u{}'.format(user),key)
	if player_play:
		player_commit,player_score = player_play.decode().split('@@')
		player_commit = player_commit.split('\n')
		player_regex = player_commit[0]
		player_sub = player_commit[1] if len(player_commit) > 1 else None
		sub_string = '\nSubstitution: `{}`'.format(player_sub) if player_sub else ''
		return '\n\n{} *Played*!\nPoints: *{}*\nRegex: `{}`{}'.format(em('tada'),player_score,player_regex,sub_string)
	else:
		return ''

def print_difficulty(difficulty):
	if difficulty == 'EASY': emj = em('four_leaf_clover')
	elif difficulty == 'NORMAL': emj = em('maple_leaf')
	elif difficulty == 'HARD': emj = em('rose')
	return '{0} *{1}* {0}'.format(emj,difficulty)

def print_tests(test_list,number):
	dots = '\n...' if number and number < len(test_list) else ''
	return '{0} *TEST* {0}\n{1}{2}'.format(em('construction'),'\n'.join(['`{}` {} `{}`'.format(s,em('arrow_forward'),t.replace('@@','')) for s,t in test_list[:number]]),dots)

def create_list_keyboard(index,range,key,admin=False):
	result,key = [],str(key) 
	if index+1 in range: result.append(InlineKeyboardButton(text=em('arrow_backward'),callback_data='list-left'))
	result.append(InlineKeyboardButton(text=em('x'),callback_data='list-cancel'))
	if index-1 in range: result.append(InlineKeyboardButton(text=em('arrow_forward'),callback_data='list-right'))
	bottom_line = [InlineKeyboardButton(text='{} Play'.format(em('video_game')),callback_data='play-regex-'+key),InlineKeyboardButton(text='{} Leaderboard'.format(em('trophy')),callback_data='scoreboard-'+key)]
	admin_line = [InlineKeyboardButton(text='{} Remove'.format(em('package')),callback_data='remove-'+key)] if admin else []
	return InlineKeyboardMarkup([result,bottom_line,admin_line])

def is_challenge_played(user,key):
	return REGEX.hget('u{}'.format(user),key)

def is_challenge_to_show(user,key):
	played = is_challenge_played(user,key)
	return not (played and not int(REGEX.hget('u{}'.format(user),'show')))

def get_challenges(user,keywords=None,difficulty=None,random=False):
	date = 10**8 if are_you_admin(user) else date_to_key()
	show = int(REGEX.hget('u{}'.format(user),'show'))
	if keywords: return [c for m,c in sorted([(search_index_from_keyword(k,keywords),int(k.decode())) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date and is_challenge_to_show(user,k)]) if m]
	if difficulty: return sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date and REGEX.hget(k,'difficulty').decode() == difficulty and is_challenge_to_show(user,k)],reverse=True)
	if random: challenges = [int(k.decode()) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date and is_challenge_to_show(user,k)]; return [choice(challenges)] if challenges else []
	return sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date and is_challenge_to_show(user,k)],reverse=True)

def search_index_from_keyword(datekey,keywords):
	descr = REGEX.hget(datekey,'descr')
	return sum([1 if k.lower() in sub(r'[*_`]','',descr.decode().lower()) else 0 for k in keywords])

def search_index_from_date(regex_list,key_date):
	return min([(abs(key_date-x),i) for i,x in enumerate(regex_list)])[1]

def delete_challenge(key):
	for k in REGEX.hkeys(key): REGEX.hdel(key,k)
	for k in REGEX.keys(): REGEX.hdel(k,key)

# Testing functions ----------------

def result_test(regex,test,answer=None,substitution=None):
	try:
		if substitution: 
			m = sub(regex,substitution,test)
			return m if not answer else m == answer
		else:
			m = search(regex,test)
			return m if not answer else m.group(1) == answer
	except (ReError, IndexError): return False
	except AttributeError: return answer == '@@'

def print_explicit_test(regex_matched,answer):
	if answer == '@@': answer = ''
	msg = '`Full match `'
	end = '`Expected   ` *{}*'.format(answer)
	if not regex_matched: return '{}\n{}'.format(msg,end)
	groups = regex_matched.groups()
	if not groups: return '{} *{}*\n{}'.format(msg,regex_matched.group(0),end)
	return '{} *{}*\n`Group1`            *{}*\n{}'.format(msg,regex_matched.group(0),groups[0],end)

def print_explicit_test_sub(substitution,answer):
	res = substitution if substitution else ''
	return '`Result    `*{}*\n`Expected  `*{}*'.format(res,answer)

def test_regex(regex,challenge_key):
	substitution = None
	if len(regex.split('\n')) == 2: regex,substitution = regex.split('\n')
	tests = [REGEX.hget(challenge_key,k).decode().split('\n') for k in sorted(REGEX.hkeys(challenge_key)) if search(r'test',str(k))]
	result = [result_test(regex,test,answer,substitution=substitution) for test,answer in tests]
	printing = ['{} _Test _`{:<2}`'.format(em('white_check_mark'),index+1) if b else '{} _Test _`{:<2}`'.format(em('no_entry_sign'),index+1) for index,b in enumerate(result)]
	if not substitution:
		result_test1 = print_explicit_test(result_test(regex,tests[0][0]),tests[0][1])
		result_test2 = print_explicit_test(result_test(regex,tests[1][0]),tests[1][1])
	else:
		result_test1 = print_explicit_test_sub(result_test(regex,tests[0][0],substitution=substitution),tests[0][1])
		result_test2 = print_explicit_test_sub(result_test(regex,tests[1][0],substitution=substitution),tests[1][1])
	score_test = sum([1 for b in result if b])/len(result)
	max_length = 104 if not substitution else 101
	score_regex = (max_length-len(regex))/100 * floor(score_test)
	score_total = (score_test*.8 + score_regex*.2) *100
	first_test,second_test,others_test = printing[0],printing[1],'\n'.join('    '.join(printing[i:i+3]) for i in range(2,len(printing[2:])+2,3))
	return round(score_total,1),'{}\n{}\n\n{}\n{}\n\n{}'.format(first_test,result_test1,second_test,result_test2,others_test)

# Profile functions ----------------

def get_users():
	return [k.decode() for k in REGEX.keys() if search('u',str(k))]

def get_leaderboard(key):
	return '\n'.join(['{}: *{}*'.format(user,score) for user,score in sorted([(REGEX.hget(u,'username').decode(),float(REGEX.hget(u,key).decode().split('@@')[1])) for u in get_users() if REGEX.hget(u,key)],key=lambda x:x[1],reverse=True)])

#--------------------------------- Utilities ------------------------------------------

def error(update, context):
	'''Log errors caused by updates.'''
	logger.warning('Update "%s" caused error "%s"', update, context.error)

#--------------------------------- Simple commands ------------------------------------

def start(update, context):
	'''Send start message. [command /start]'''
	user = update.message.from_user
	telegram_id = update.message.chat.id
	db_name = update.message.from_user.username if update.message.from_user.username else user.first_name
	REGEX.hset('u{}'.format(telegram_id),'username',db_name)
	REGEX.hset('u{}'.format(telegram_id),'show',1)
	update.message.reply_text('Welcome {}!\nI\'m `Regexo`, your worst regular expression nightmare.\n\nUse /help to know how to survive.'.format(user.first_name),parse_mode='Markdown')

def help(update, context):
	'''Send help message. [command /help]'''
	update.message.reply_text(	'*Q*: _How the _*regex*_ works?_\n*A*: _You need to match everything the text said to you in the first group of the regex._\n\n'
								'*Q*: _Which _*commands*_ can I use?_\n*A*: _For now, you can use _/challenges_ to play or _/search_ to find a challenge by keywords._\n\n'
								'*Q*: _Why can\'t I see the challenges I _*played*_?_\n*A*: _You can use _/togglePlayed_ to show/hide the played challenges._\n\n'
								'*Q*: _Where can I send my _*complaints*_?_\n*A*: _There, to _[Mortafix](https://t.me/mortafix)_!_',parse_mode='Markdown')

def cancel(update, context):
	'''User cancel conversation, exit gently'''
	user = update.message.from_user
	update.message.reply_text('Why *{}*? {}'.format(user.first_name,em('sob')),parse_mode='Markdown')
	return ConversationHandler.END

#--------------------------------- Handler --------------------------------------------

def handle_text(update, context):
	'''Handler for a non-command message.'''
	update.message.reply_text('{} Hey *{}*.. not today, maybe not even tomorrow, but definitely one day this command will do something...'.format(em('x'),update.message.from_user.first_name),parse_mode='Markdown')

#--------------------------------- Commands -------------------------------------------

# ADD REGEX (admin) ---------------------------------

def new_regex(update,context):
	'''/newregex - Choose date'''
	telegram_id = update.message.chat.id
	are_you_alive(telegram_id,update.message.from_user)
	if not are_you_admin(telegram_id): update.message.reply_text('{} *STOP NOW*!\nYou aren\'t Admin Gang auh.'.format(em('no_entry_sign')),parse_mode='Markdown'); return ConversationHandler.END
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Today'.format(em('pushpin')),callback_data='regex-date-today'),InlineKeyboardButton(text='{} Another Date'.format(em('crystal_ball')),callback_data='regex-date-another')]])
	update.message.reply_text('{} Choose challenge *date* _or_\n{} Upload a *file*.'.format(em('date'),em('page_facing_up')),reply_markup=reply_keyboard,parse_mode='Markdown')
	return DATE_CHOOSE

def add_difficulty(update,context):
	''''/newrex - Add difficulty'''
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} EASY'.format(em('four_leaf_clover')),callback_data='difficulty-easy'),InlineKeyboardButton(text='{} NORMAL'.format(em('maple_leaf')),callback_data='difficulty-medium'),InlineKeyboardButton(text='{} HARD'.format(em('rose')),callback_data='difficulty-hard')]])
	if update.callback_query:
		telegram_id = update.callback_query.message.chat.id
		context.user_data.update({telegram_id:'difficulty'})
		update.callback_query.edit_message_text('{} Select *difficulty*.\n'.format(em('dart')),reply_markup=reply_keyboard, parse_mode='Markdown')
		return LIST_C
	else:
		telegram_id = update.message.chat.id
		date = update.message.text
		try: date_key = date_to_key(date)
		except ValueError: update.message.reply_text('{} Wrong date!\n\n{} Try again.\n\[dd-mm-yyyy]'.format(em('x'),em('date')),parse_mode='Markdown'); return ADD_DIFFICULTY
		if challenge_exists(date_key): update.message.reply_text('{} Challenge already exists on this date.'.format(em('no_entry'))); return ConversationHandler.END
		context.user_data.update({telegram_id:{'regex-date':date_key,'index-test':1}})
		update.message.reply_text('{} Select *difficulty*.\n'.format(em('dart')),reply_markup=reply_keyboard, parse_mode='Markdown')
		return ADD_DESCRIPTION

def add_description(update,context):
	'''/newregex - Add description'''
	query = update.callback_query
	telegram_id = query.message.chat.id
	query.answer()
	if query.data == 'difficulty-easy': difficulty = 'EASY' 
	elif query.data == 'difficulty-medium': difficulty = 'NORMAL'
	elif query.data == 'difficulty-hard': difficulty = 'HARD' 
	d_key = context.user_data.get(telegram_id).get('regex-date')
	if d_key not in REGEX: REGEX.hset(d_key,'difficulty',difficulty)
	query.edit_message_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
	return ADD_TEST

def add_test(update,context):
	'''/newregex - Choose a new test or stop'''
	telegram_id = update.message.chat.id
	msg = ''
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Add test'.format(em('heavy_plus_sign')),callback_data='test-new'),InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='test-stop')]])
	d_key = context.user_data.get(telegram_id).get('regex-date')
	if not REGEX.hexists(d_key,'descr'): REGEX.hset(d_key,'descr',update.message.text)
	else:
		test = tuple(update.message.text.split('\n'))
		if len(test) != 2: msg = '{} Wrong format!\n\n'.format(em('x'))
		else:
			idx = context.user_data.get(telegram_id).get('index-test')
			REGEX.hset(d_key,'test{:02d}'.format(idx),update.message.text)
			context.user_data.get(telegram_id).update({'index-test':idx+1})
			msg = '{} Test *{}* added!\n\n'.format(em('white_check_mark'),idx)
	update.message.reply_text(msg+'Do you want to add a new *test*?',reply_markup=reply_keyboard,parse_mode='Markdown')
	return NEW_TEST

def new_test(update,context):
	'''/newregex - Add test'''
	query = update.callback_query
	telegram_id = query.message.chat.id
	query.answer()
	if query.data == 'test-new': query.edit_message_text('{} Add new *test*.\n\nLine 1: `Test string`\nLine 2: `Answer`'.format(em('floppy_disk')),parse_mode='Markdown'); return ADD_TEST
	elif query.data == 'test-stop': query.edit_message_text('{} Challenge added!\n\n{}'.format(em('tada'),print_challenge(key=context.user_data.get(telegram_id).get('regex-date'),usr_id=telegram_id)),parse_mode='Markdown'); return ConversationHandler.END

# LIST REGEX --------------------------------

def list_request(update,context):
	'''/challenges - Choose date'''
	telegram_id = update.message.chat.id
	are_you_alive(telegram_id,update.message.from_user)
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Today'.format(em('pushpin')),callback_data='list-date-today'),InlineKeyboardButton(text='{} Another Date'.format(em('crystal_ball')),callback_data='list-date-another')],[InlineKeyboardButton('{} Difficulty'.format(em('dart')),callback_data='list-difficulty'),InlineKeyboardButton('{} Random'.format(em('game_die')),callback_data='list-random')]])
	update.message.reply_text('{} Choose a *challenge* to play.'.format(em('date')),reply_markup=reply_keyboard,parse_mode='Markdown')
	return DATE_CHOOSE

def list_regex(update,context):
	'''Show regex challenges'''
	if update.callback_query:
		telegram_id = update.callback_query.message.chat.id
		data = context.user_data.get(telegram_id)
		# callback data
		challenge_key = search(r'(?:play-regex-)(\d+)',update.callback_query.data)
		scoreboard_key = search(r'(?:scoreboard-)(\d+)',update.callback_query.data)
		remove_key = search(r'(?:remove-)(\d+)',update.callback_query.data) 
		# PLAY Button
		if challenge_key:
			history = REGEX.hget('u{}'.format(telegram_id),challenge_key.group(1))
			max_score = float(history.decode().split('@@')[1]) if history else 0
			data.update({'play':challenge_key.group(1),'score':max_score})
			keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Preview'.format(em('mag')),callback_data='preview'),InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='end')]])
			update.callback_query.edit_message_text('{} Challenge started!\n\nInsert your *regex*\n(and a *substitution* if needed)'.format(em('zap')),reply_markup=keyboard,parse_mode='Markdown'); return PLAY 
		# SCOREBOARD Button
		elif scoreboard_key:
			history = REGEX.hget('u{}'.format(telegram_id),scoreboard_key.group(1))
			max_score = float(history.decode().split('@@')[1]) if history else 0
			data.update({'play':scoreboard_key.group(1),'score':max_score})
			keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Play'.format(em('video_game')),callback_data='play-regex')],[InlineKeyboardButton(text='{} Back'.format(em('arrow_left')),callback_data='back'),InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='end')]])
			update.callback_query.edit_message_text('{0} *LEADERBOARD* {0}\n\n{1}'.format(em('trophy'),get_leaderboard(scoreboard_key.group(1))),reply_markup=keyboard,parse_mode='Markdown'); return PLAY_DISPACTHER
		# REMOVE button
		elif remove_key:
			delete_challenge(remove_key.group(1))
			update.callback_query.edit_message_text('{} Challenge remove correctly'.format(em('new_moon_with_face'))); return ConversationHandler.END
		# from TODAY (date choose)
		elif 'list-date' in data:
			regex_past = get_challenges(telegram_id)
			list_range = list(range(0,len(regex_past)))
			if regex_past:
				idx = search_index_from_date(regex_past,data.get('list-date'))
				context.user_data.update({telegram_id:{'list-id':idx,'list-regex':regex_past,'list-range':list_range}})
				reply_markup = create_list_keyboard(idx,list_range,regex_past[idx],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=regex_past,index=idx,number=2,usr_id=telegram_id)
				ret = LIST_C
			else: 
				reply_markup = None
				msg = '{} No challenges yet.\n_Please rompere i maroni alla direzione_'.format(em('zzz'))
				ret = ConversationHandler.END
			update.callback_query.edit_message_text(msg,reply_markup=reply_markup,parse_mode='Markdown')
			return ret
		# from RANDOM
		elif 'random' in data:
			regex_past = get_challenges(telegram_id,random=True)
			list_range = list(range(0,len(regex_past)))
			if regex_past:
				idx = len(regex_past)-1
				context.user_data.update({telegram_id:{'list-id':idx,'list-regex':regex_past,'list-range':list_range}})
				reply_markup = create_list_keyboard(idx,list_range,regex_past[idx],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=regex_past,index=idx,number=2,usr_id=telegram_id)
				ret = LIST_C
			else: 
				reply_markup = None
				msg = '{} All challenges played!'.format(em('100'))
				ret = ConversationHandler.END
			update.callback_query.edit_message_text(msg,reply_markup=reply_markup,parse_mode='Markdown')
			return ret
		# from DIFFICULTY
		elif 'difficulty' in data:
			query = update.callback_query
			if query.data == 'difficulty-easy': difficulty = 'EASY' 
			elif query.data == 'difficulty-medium': difficulty = 'NORMAL'
			elif query.data == 'difficulty-hard': difficulty = 'HARD'
			regex_past = get_challenges(telegram_id,difficulty=difficulty)
			list_range = list(range(0,len(regex_past)))
			if regex_past:
				idx = len(regex_past)-1
				context.user_data.update({telegram_id:{'list-id':idx,'list-regex':regex_past,'list-range':list_range}})
				reply_markup = create_list_keyboard(idx,list_range,regex_past[idx],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=regex_past,index=idx,number=2,usr_id=telegram_id)
				ret = LIST_C
			else: 
				reply_markup = None
				msg = '{} All *{}* challenges played!'.format(em('100'),difficulty)
				ret = ConversationHandler.END
			query.edit_message_text(msg,reply_markup=reply_markup,parse_mode='Markdown')
			return ret
		# from InlineKeyboard (list)
		else:	
			list_id,list_regex,list_range = data['list-id'],data['list-regex'],data['list-range']
			query = update.callback_query
			user = query.from_user
			query.answer()
			if query.data == 'list-right':
				context.user_data.get(telegram_id).update({'list-id':list_id-1})
				reply_keyboard = create_list_keyboard(list_id-1,list_range,list_regex[list_id-1],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=list_regex,index=list_id-1,number=2,usr_id=telegram_id)
				query.edit_message_text(msg,reply_markup=reply_keyboard,parse_mode='Markdown')
			elif query.data == 'list-left':
				context.user_data.get(telegram_id).update({'list-id':list_id+1})
				reply_keyboard = create_list_keyboard(list_id+1,list_range,list_regex[list_id+1],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=list_regex,index=list_id+1,number=2,usr_id=telegram_id)
				query.edit_message_text(msg,reply_markup=reply_keyboard,parse_mode='Markdown')
			elif query.data == 'back':
				context.user_data.get(telegram_id).update({'list-id':list_id})
				reply_keyboard = create_list_keyboard(list_id,list_range,list_regex[list_id],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=list_regex,index=list_id,number=2,usr_id=telegram_id)
				query.edit_message_text(msg,reply_markup=reply_keyboard,parse_mode='Markdown')
			elif query.data == 'list-cancel': query.edit_message_text('{} *{}* goes brrrr!'.format(em('dash'),user.first_name),parse_mode='Markdown'); return ConversationHandler.END
	# from ANOTHER DATE (date choose)
	else:
		telegram_id = update.message.chat.id
		if context.user_data.get(telegram_id) == 'keywords':
			keywords = update.message.text.split()
			challenges = get_challenges(telegram_id,keywords=keywords)
			if challenges:
				idx = len(challenges)-1
				list_range = list(range(0,idx+1))
				context.user_data.update({telegram_id:{'list-id':idx,'list-regex':challenges,'list-range':list_range}})
				reply_markup = create_list_keyboard(idx,list_range,challenges[idx],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=challenges,index=idx,number=2,usr_id=telegram_id)
				ret = LIST_C
			else: 
				reply_markup = None
				msg = '{} No challenges found with these *keywords*.'.format(em('mag'))
				ret = ConversationHandler.END
		else:
			date = update.message.text
			try: date_key = date_to_key(date)
			except ValueError: update.message.reply_text('{} Wrong date!\n\n{} Try again.\n\[dd-mm-yyyy]'.format(em('x'),em('date')),parse_mode='Markdown'); return LIST_M
			regex_past = get_challenges(telegram_id)
			list_range = list(range(0,len(regex_past)))
			if regex_past:
				idx = search_index_from_date(regex_past,date_key)
				context.user_data.update({telegram_id:{'list-id':idx,'list-regex':regex_past,'list-range':list_range}})
				reply_markup = create_list_keyboard(idx,list_range,regex_past[idx],admin=are_you_admin(telegram_id))
				msg = print_challenge(regex_list=regex_past,index=idx,number=2,usr_id=telegram_id)
				ret = LIST_C
			else: 
				reply_markup = None
				msg = '{} No challenges yet.\n_Please rompere i maroni alla direzione_'.format(em('zzz'))
				ret = ConversationHandler.END
		update.message.reply_text(msg,reply_markup=reply_markup,parse_mode='Markdown')
		return ret

# PLAY --------------------------------------------------------

def play_dispatcher(update,context):
	query = update.callback_query
	telegram_id = query.message.chat.id
	score = context.user_data.get(telegram_id).get('score')
	if query.data == 'play-regex':
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Preview'.format(em('mag')),callback_data='preview'),InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='end')]])
		query.edit_message_text('{} Challenge started!\n\nInsert your *regex*\n(and a *substitution* if needed)'.format(em('zap')),reply_markup=keyboard,parse_mode='Markdown')
		return PLAY
	elif query.data == 'back': list_regex(update,context); return LIST_C
	elif query.data == 'end': query.edit_message_text('{} Challenge completed!\nScore: *{}*'.format(em('tada'),score),parse_mode='Markdown'); return ConversationHandler.END
	else: query.edit_message_text('Telegram bot goes bbrrrrrr <3'); return ConversationHandler.END 

def play_challenge(update,context):
	if update.callback_query:
		query = update.callback_query
		telegram_id = update.callback_query.message.chat.id
		score = context.user_data.get(telegram_id).get('score')
		challenge_key = context.user_data.get(telegram_id).get('play')
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='end')]])
		if query.data == 'preview': query.edit_message_text('{}\n\nInsert your *regex* to play\n(and a *substitution* if needed)'.format(print_challenge(key=challenge_key,number=2,usr_id=telegram_id)),reply_markup=keyboard,parse_mode='Markdown'); return PLAY
		elif query.data == 'end': query.edit_message_text('{} Challenge completed!\nScore: *{}*'.format(em('tada'),score),parse_mode='Markdown'); return ConversationHandler.END
	else:
		telegram_id = update.message.chat.id
		challenge_key = context.user_data.get(telegram_id).get('play')
		regex = update.message.text
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} Preview'.format(em('mag')),callback_data='preview'),InlineKeyboardButton(text='{} End'.format(em('x')),callback_data='end')]])
		score_regex,tests = test_regex(regex,challenge_key)
		if score_regex > context.user_data.get(telegram_id).get('score'):
			context.user_data.get(telegram_id).update({'score':score_regex})
			REGEX.hset('u{}'.format(telegram_id),challenge_key,'{}@@{}'.format(regex,score_regex))
		score = context.user_data.get(telegram_id).get('score')
		update.message.reply_text('Regex: `{}`\nMax score: *{}*\nCurrent score: *{}*\n\n{}'.format(regex,score,score_regex,tests),reply_markup=keyboard,parse_mode='Markdown'); return PLAY
# SEARCH ------------------------------------------------------

def search_request(update,context):
	telegram_id = update.message.chat.id
	context.user_data.update({telegram_id:'keywords'})
	update.message.reply_text('{} Insert *one or more keywords* to find a challenge.\n(separated by a space)'.format(em('key')),parse_mode='Markdown')
	return LIST_M

# TOGGLE PLAYED -----------------------------------------------

def toggle_played(update,context):
	telegram_id = update.message.chat.id
	show = int(REGEX.hget('u{}'.format(telegram_id),'show'))
	REGEX.hset('u{}'.format(telegram_id),'show',(0,1)[not show])
	msg = '{} Toggle played *OFF*!\n_CLEANING CONTACTS TIME_\nNow, all the played challenges are hidden.'.format(em('see_no_evil')) if show else '{} Toggle played *ON*!\n_REFACTOR TIME_\nNow, you can see all the challenges, including those played.'.format(em('hear_no_evil'))
	update.message.reply_text(msg,parse_mode='Markdown')

# FILE --------------------------------------------------------

def get_challenge_from_file(update,context):
	telegram_id = update.message.chat.id
	file = context.bot.get_file(update.message.document).download()
	lines = open(file,'r').read().split('\n')
	# parser
	try: date_key = date_to_key(lines[0])
	except ValueError: update.message.reply_text('{} Please check *date* format in file.\nMust be [dd-mm-yyy]'.format(em('no_entry')),parse_mode='Markdown'); return ConversationHandler.END
	if challenge_exists(date_key): update.message.reply_text('{} Challenge already exists on this date.'.format(em('no_entry'))); return ConversationHandler.END
	difficulty = lines[1].upper()
	descr = lines[2]
	if difficulty not in ['EASY','NORMAL','HARD']: update.message.reply_text('{} Invalid difficulty level. Must be *EASY*, *NORMAL*, or *HARD*.'.format(em('no_entry')),parse_mode='Markdown'); return ConversationHandler.END
	test = [l for l in lines[3:] if l]
	if len(test) % 2 != 0: update.message.reply_text('{} Please check *tests*.\nMust be two lines for each test.'.format(em('no_entry')),parse_mode='Markdown'); return ConversationHandler.END
	REGEX.hset(date_key,'descr',descr)
	REGEX.hset(date_key,'difficulty',difficulty)
	for i,t in enumerate(test):
		if not i%2: REGEX.hset(date_key,'test{:02d}'.format(i//2+1),'{}\n{}'.format(t,test[i+1])) 
	update.message.reply_text('{} Challenge added!\n\n{}'.format(em('tada'),print_challenge(key=date_key,usr_id=telegram_id)),parse_mode='Markdown')
	return ConversationHandler.END

# DATE --------------------------------------------------------

def date_dispatcher(update,context):
	'''Request Date'''
	telegram_id = update.callback_query.message.chat.id
	query = update.callback_query
	query.answer()
	if query.data == 'regex-date-today':
		if challenge_exists(date_to_key()): query.edit_message_text('{} Challenge already exists on this date.'.format(em('no_entry'))); return ConversationHandler.END
		reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='{} EASY'.format(em('four_leaf_clover')),callback_data='difficulty-easy'),InlineKeyboardButton(text='{} NORMAL'.format(em('maple_leaf')),callback_data='difficulty-medium'),InlineKeyboardButton(text='{} HARD'.format(em('rose')),callback_data='difficulty-hard')]])
		query.edit_message_text('{} Select *difficulty*.\n'.format(em('dart')),reply_markup=reply_keyboard, parse_mode='Markdown')
		#query.edit_message_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
		context.user_data.update({telegram_id:{'regex-date':date_to_key(),'index-test':1}})
		return ADD_DESCRIPTION
	elif query.data == 'regex-date-another': query.edit_message_text('{} Insert *date*.\n\[dd-mm-yyyy]'.format(em('date')),parse_mode='Markdown'); return ADD_DIFFICULTY
	elif query.data == 'list-date-today': context.user_data.update({telegram_id:{'list-date':date_to_key()}}); return list_regex(update,context)
	elif query.data == 'list-date-another': query.edit_message_text('{} Insert *date*.\n\[dd-mm-yyyy]'.format(em('date')),parse_mode='Markdown'); return LIST_M
	elif query.data == 'list-random': context.user_data.update({telegram_id:'random'}); return list_regex(update,context)
	elif query.data == 'list-difficulty': return add_difficulty(update,context)

# MAIN ----------------------------------------------------------------------------------

def main():
	'''Bot instance'''
	pp = PicklePersistence(filename='rgx_persistence')
	updater = Updater(TOKEN, persistence=pp, use_context=True)
	dp = updater.dispatcher

	# -----------------------------------------------------------------------
 
	# commands
	cmd_start = CommandHandler("start", start)
	cmd_help = CommandHandler("help", help)
	cmd_debug = CommandHandler("debug",debug_redis)
	cmd_togglePlayed = CommandHandler("togglePlayed",toggle_played)

	# conversations
	conv_new_regex = ConversationHandler(
		entry_points = [CommandHandler('regex',new_regex)],
		states = {
			ADD_DIFFICULTY: [MessageHandler(Filters.text,add_difficulty)],
			ADD_DESCRIPTION: [CallbackQueryHandler(add_description)],
			ADD_TEST: [MessageHandler(Filters.text,add_test)],
			DATE_CHOOSE: [CallbackQueryHandler(date_dispatcher),MessageHandler(Filters.document,get_challenge_from_file)],
			NEW_TEST: [CallbackQueryHandler(new_test)]
		},
		fallbacks=[CommandHandler('cancel',cancel)],
		name='login-conversation',
		persistent=True
		)

	conv_list = ConversationHandler(
		entry_points = [CommandHandler("challenges",list_request)],
		states = {
			DATE_CHOOSE: [CallbackQueryHandler(date_dispatcher)],
			LIST_C: [CallbackQueryHandler(list_regex)],
			LIST_M: [MessageHandler(Filters.text,list_regex)],
			PLAY: [MessageHandler(Filters.text,play_challenge),CallbackQueryHandler(play_challenge)],
			PLAY_DISPACTHER: [CallbackQueryHandler(play_dispatcher)]
		},
		fallbacks = [CommandHandler("cancel",cancel)],
		name='list-conversation',
		persistent=True
		)

	conv_search = ConversationHandler(
		entry_points = [CommandHandler("search",search_request)],
		states = {
			LIST_C: [CallbackQueryHandler(list_regex)],
			LIST_M: [MessageHandler(Filters.text,list_regex)],
			PLAY: [MessageHandler(Filters.text,play_challenge),CallbackQueryHandler(play_challenge)],
			PLAY_DISPACTHER: [CallbackQueryHandler(play_dispatcher)]
		},
		fallbacks = [CommandHandler("cancel",cancel)],
		name='search-conversation',
		persistent=True
		)

	# -----------------------------------------------------------------------

	# handlers - commands and conversations
	dp.add_handler(conv_new_regex)
	dp.add_handler(conv_list)
	dp.add_handler(conv_search)
	dp.add_handler(cmd_start)
	dp.add_handler(cmd_help)
	dp.add_handler(cmd_debug)
	dp.add_handler(cmd_togglePlayed)

	# handlers - no command
	dp.add_handler(MessageHandler(Filters.text,handle_text))

	# handlers - error
	dp.add_error_handler(error)

	# ----------------------------------------------------------------------

	if TERMINAL:
		updater.start_polling()
	else:
		updater.start_webhook(listen="0.0.0.0",port=int(PORT),url_path=TOKEN)
		updater.bot.setWebhook('https://regexo-bot.herokuapp.com/'+TOKEN)
	print('Bot started!')

	# Run the bot until you press Ctrl-C
	updater.idle()

if __name__ == '__main__':
	main()