import logging
import os
from telegram import ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, PicklePersistence
from emoji import emojize
from datetime import date
from re import match,search
from re import error as ReError
import redis


# Enable logging and port
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
logger = logging.getLogger(__name__)
PORT = int(os.environ.get('PORT', 5000))
# Config variables
TOKEN = '1178476105:AAEeuMbyRQ5blEM11V0xtqEkiMsDGhnikyU'
ADD_TEST,NEW_TEST,ADD_DESCRIPTION,DATE_CHOOSE,LIST_C,LIST_M,PLAY,PLAY_DISPACTHER = range(8)
# Redis Setup
REGEX = redis.from_url(os.environ.get("REDIS_URL"))
#REGEX = redis.Redis(host='localhost', port=6379, db=0) # terminal debugging

#--------------------------------- Functions ------------------------------------------

# Base function ---------------------------

def debug_redis(update,context):
	telegram_id = update.message.chat.id
	if are_you_admin(telegram_id):
		msg = '\n\n'.join(['{}\n{}'.format(k.decode(),'\n'.join(['{}: {}'.format(key.decode(),REGEX.hget(k,key).decode().replace('\n',' > ')) for key in REGEX.hkeys(k)])) for k in sorted(REGEX.keys())])
		with open('debug.txt','w') as f: f.write(msg)
		update.message.reply_document(document=open('debug.txt', 'rb'))

def date_to_key(date_key=None):
	date_key =  date.today() if not date_key else date.fromisoformat('-'.join(date_key.split('-')[::-1]))
	return int('{:04d}{:02d}{:02d}'.format(date_key.year,date_key.month,date_key.day))

def key_to_date(key):
	return '{2}.{1}.{0}'.format(key[0:4],key[4:6],key[6:8])

def em(emoji_string):
	return emojize(':'+emoji_string+':',use_aliases=True)

def are_you_admin(telegram_id):
	return telegram_id in [18528224,]

def challenge_exists(key):
	return key in REGEX

def are_you_alive(telegram_id,user):
	if 'u{}'.format(telegram_id) not in get_users():
		db_name = user.username if user.username else user.first_name
		REGEX.hset('u{}'.format(telegram_id),'username',db_name)

# Playing function ---------------------------

def print_challenge(regex_list=None,index=None,key=None,number=None,usr_id=None):
	if regex_list: key = regex_list[index]
	descr = REGEX.hget(key,'descr').decode()
	test = [REGEX.hget(key,k).decode().split('\n') for k in sorted(REGEX.hkeys(key)) if search(r'test',str(k))]
	k = key
	player_score = REGEX.hget('u{}'.format(usr_id),key)
	player = '\n\n{} Played!\nPoints: *{}*\nRegex: `{}`'.format(em('tada'),player_score.decode().split('@@')[1],player_score.decode().split('@@')[0]) if player_score else ''
	return '\[{}]\n{} {}\n\n{}{}'.format(key_to_date(str(k)),em('bell'),descr,print_tests(test,number),player)

def print_tests(test_list,number):
	dots = '\n...' if number and number < len(test_list) else ''
	return '\n'.join(['`{}` {} `{}`'.format(s,em('arrow_forward'),t.replace('@@','')) for s,t in test_list[:number]])+dots

def create_list_keyboard(index,range,key,admin=False):
	result,key = [],str(key) 
	if index+1 in range: result.append(InlineKeyboardButton(text=em('arrow_backward'),callback_data='list-left'))
	result.append(InlineKeyboardButton(text=em('x'),callback_data='list-cancel'))
	if index-1 in range: result.append(InlineKeyboardButton(text=em('arrow_forward'),callback_data='list-right'))
	bottom_line = [InlineKeyboardButton(text='Play',callback_data='play-regex-'+key),InlineKeyboardButton(text='Leaderboard',callback_data='scoreboard-'+key)]
	admin_line = [InlineKeyboardButton(text='Remove',callback_data='remove-'+key)] if admin else []
	return InlineKeyboardMarkup([result,bottom_line,admin_line])

def search_index_from_date(regex_list,key_date):
	return min([(abs(key_date-x),i) for i,x in enumerate(regex_list)])[1]

def delete_challenge(key):
	for k in REGEX.hkeys(key): REGEX.hdel(key,k)
	for k in REGEX.keys(): REGEX.hdel(k,key)

# Testing functions ----------------

def result_test(regex,test,answer):
	try: return search(regex,test).group(1) == answer
	except (AttributeError, IndexError, ReError): return answer == '@@'

def test_regex(regex,challenge_key):
	tests = [REGEX.hget(challenge_key,k).decode().split('\n') for k in REGEX.hkeys(challenge_key) if search(r'test',str(k))]
	result = [result_test(regex,test,answer) for test,answer in tests]
	printing = ['{} _Test {}_'.format(em('white_check_mark'),index) if b else '{} Test {}.'.format(em('no_entry_sign'),index) for index,b in enumerate(result)]
	score = sum([1 for b in result if b])/len(result)*(104-len(regex))
	return round(score,1),'\n'.join(printing)

# Profile functions ----------------

def get_users():
	return [k for k in REGEX.keys() if search('u',str(k))]

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
    update.message.reply_text('Welcome {}!\nI\'m `Regexo`, your worst regular expression nightmare.'.format(user.first_name),parse_mode='Markdown')

def help(update, context):
    '''Send help message. [command /help]'''
    update.message.reply_text('{} Help goes brrrr..'.format(emojize(':raised_hand:',use_aliases=True)))

def cancel(update, context):
    '''User cancel conversation, exit gently'''
    user = update.message.from_user
    update.message.reply_text('Why *{}*? {}'.format(user.first_name,em('sob')),parse_mode='Markdown')
    return ConversationHandler.END

#--------------------------------- Handler --------------------------------------------

def handle_text(update, context):
	'''Handler for a non-command message.'''
	update.message.reply_text('{} Hey *{}*, non sembra un comado accettabile questo...'.format(em('x'),update.message.from_user.first_name),parse_mode='Markdown')

#--------------------------------- Commands -------------------------------------------

# ADD REGEX (admin) ---------------------------------

def new_regex(update,context):
	'''/newregex - Choose date'''
	telegram_id = update.message.chat.id
	are_you_alive(telegram_id,update.message.from_user)
	if not are_you_admin(telegram_id): update.message.reply_text('{} *STOP NOW*!\nYou aren\'t Admin Gang auh.'.format(em('no_entry_sign')),parse_mode='Markdown'); return ConversationHandler.END
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Today',callback_data='regex-date-today'),InlineKeyboardButton(text='Another Date',callback_data='regex-date-another')]])
	update.message.reply_text('{} Choose challenge *date*.'.format(em('date')),reply_markup=reply_keyboard,parse_mode='Markdown')
	return DATE_CHOOSE

def add_description(update,context):
	'''/newregex - Add description'''
	telegram_id = update.message.chat.id
	date = update.message.text
	try: date_key = date_to_key(date)
	except ValueError: update.message.reply_text('{} Wrong date!\n\nTry again.\n\[dd-mm-yyyy]'.format(em('x')),parse_mode='Markdown'); return ADD_DESCRIPTION
	if challenge_exists(date_key): query.edit_message_text('{} Challenge already exists on this date.'.format(em('no_entry'))); return ConversationHandler.END
	context.user_data.update({telegram_id:{'regex-date':date_key,'index-test':1}})
	update.message.reply_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
	return ADD_TEST

def add_test(update,context):
	'''/newregex - Choose a new test or stop'''
	telegram_id = update.message.chat.id
	msg = ''
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Add test',callback_data='test-new'),InlineKeyboardButton(text='End',callback_data='test-stop')]])
	d_key = context.user_data.get(telegram_id).get('regex-date')
	if d_key not in REGEX: REGEX.hset(d_key,'descr',update.message.text)
	else:
		test = tuple(update.message.text.split('\n'))
		if len(test) != 2: msg = '{} Wrong format!\n\n'.format(em('x'))
		else:
			idx = context.user_data.get(telegram_id).get('index-test')
			REGEX.hset(d_key,'test{}'.format(idx),update.message.text)
			context.user_data.get(telegram_id).update({'index-test':idx+1})
			msg = '{} Test added!\n\n'.format(em('white_check_mark'))
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
	'''/newregex - Choose date'''
	telegram_id = update.message.chat.id
	are_you_alive(telegram_id,update.message.from_user)
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Today',callback_data='list-date-today'),InlineKeyboardButton(text='Another Date',callback_data='list-date-another')]])
	update.message.reply_text('{} Choose a *challenge* to view.'.format(em('date')),reply_markup=reply_keyboard,parse_mode='Markdown')
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
			keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Preview',callback_data='preview'),InlineKeyboardButton(text='End',callback_data='end')]])
			update.callback_query.edit_message_text('{} Challenge started!\n\nInsert your *regex*.'.format(em('zap')),reply_markup=keyboard,parse_mode='Markdown'); return PLAY 
		# SCOREBOARD Button
		elif scoreboard_key:
			history = REGEX.hget('u{}'.format(telegram_id),scoreboard_key.group(1))
			max_score = float(history.decode().split('@@')[1]) if history else 0
			data.update({'play':scoreboard_key.group(1),'score':max_score})
			keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Play',callback_data='play-regex'),InlineKeyboardButton(text='End',callback_data='end')],[InlineKeyboardButton(text='Back',callback_data='back')]])
			update.callback_query.edit_message_text('{0} *LEADERBOARD* {0}\n\n{1}'.format(em('trophy'),get_leaderboard(scoreboard_key.group(1))),reply_markup=keyboard,parse_mode='Markdown'); return PLAY_DISPACTHER
		# REMOVE button
		elif remove_key:
			delete_challenge(remove_key.group(1))
			update.callback_query.edit_message_text('{} Challenge remove correctly'.format(em('new_moon_with_face'))); return ConversationHandler.END
		# from TODAY (date choose)
		elif 'list-date' in data:
			if are_you_admin(telegram_id): regex_past = sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k))],reverse=True)
			else: regex_past = sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date_to_key()],reverse=True)
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
		date = update.message.text
		try: date_key = date_to_key(date)
		except ValueError: update.message.reply_text('{} Wrong date!\n\nTry again.\n\[dd-mm-yyyy]'.format(em('x')),parse_mode='Markdown'); return LIST_M
		if are_you_admin(telegram_id): regex_past = sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k))],reverse=True)
		else: regex_past = sorted([int(k.decode()) for k in REGEX.keys() if not search('u',str(k)) and int(k) <= date_to_key()],reverse=True)
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
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Preview',callback_data='preview'),InlineKeyboardButton(text='End',callback_data='end')]])
		query.edit_message_text('{} Challenge started!\n\nInsert your *regex*.'.format(em('zap')),reply_markup=keyboard,parse_mode='Markdown')
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
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='End',callback_data='end')]])
		if query.data == 'preview': query.edit_message_text('{}\n\nInsert your *regex* to play.'.format(print_challenge(key=challenge_key,number=2,usr_id=telegram_id)),reply_markup=keyboard,parse_mode='Markdown'); return PLAY
		elif query.data == 'end': query.edit_message_text('{} Challenge completed!\nScore: *{}*'.format(em('tada'),score),parse_mode='Markdown'); return ConversationHandler.END
	else:
		telegram_id = update.message.chat.id
		challenge_key = context.user_data.get(telegram_id).get('play')
		regex = update.message.text
		keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Preview',callback_data='preview'),InlineKeyboardButton(text='End',callback_data='end')]])
		score_regex,tests = test_regex(regex,challenge_key)
		if score_regex > context.user_data.get(telegram_id).get('score'):
			context.user_data.get(telegram_id).update({'score':score_regex})
			REGEX.hset('u{}'.format(telegram_id),challenge_key,'{}@@{}'.format(regex,score_regex))
		score = context.user_data.get(telegram_id).get('score')
		update.message.reply_text('Regex: `{}`\nMax score: *{}*\nCurrent score: *{}*\n\n{}'.format(regex,score,score_regex,tests),reply_markup=keyboard,parse_mode='Markdown'); return PLAY

# FILE --------------------------------------------------------

def get_challenge_from_file(update,context):
	telegram_id = update.message.chat.id
	file = context.bot.get_file(update.message.document).download()
	lines = open(file,'r').read().split('\n')
	# parser
	try: date_key = date_to_key(lines[0])
	except ValueError: update.message.reply_text('{} Please check *date* format in file.\nMust be [dd-mm-yyy]'.format(em('no_entry')),parse_mode='Markdown'); return ConversationHandler.END
	if challenge_exists(date_to_key()): update.message.reply_text('{} Challenge already exists on this date.'.format(em('no_entry'))); return ConversationHandler.END
	descr = lines[1]
	test = [l for l in lines[2:] if l]
	if len(test) % 2 != 0: update.message.reply_text('{} Please check *tests*.\nMust be two lines for each test.'.format(em('no_entry')),parse_mode='Markdown'); return ConversationHandler.END
	REGEX.hset(date_key,'descr',descr)
	for i,t in enumerate(test):
		if not i%2: REGEX.hset(date_key,'test{}'.format(i//2+1),'{}\n{}'.format(t,test[i+1])) 
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
		query.edit_message_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
		context.user_data.update({telegram_id:{'regex-date':date_to_key(),'index-test':1}})
		return ADD_TEST
	elif query.data == 'regex-date-another': query.edit_message_text('Insert *date*.\n\[dd-mm-yyyy]',parse_mode='Markdown'); return ADD_DESCRIPTION
	elif query.data == 'list-date-today': context.user_data.update({telegram_id:{'list-date':date_to_key()}}); return list_regex(update,context)
	elif query.data == 'list-date-another': query.edit_message_text('Insert *date*.\n\[dd-mm-yyyy]',parse_mode='Markdown'); return LIST_M

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

    # conversations
    conv_new_regex = ConversationHandler(
    	entry_points = [CommandHandler('regex',new_regex)],
    	states = {
    		ADD_DESCRIPTION: [MessageHandler(Filters.text,add_description)],
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

    # -----------------------------------------------------------------------

    # handlers - commands and conversations
    dp.add_handler(conv_new_regex)
    dp.add_handler(conv_list)
    dp.add_handler(cmd_start)
    dp.add_handler(cmd_help)
    dp.add_handler(cmd_debug)

    # handlers - no command
    dp.add_handler(MessageHandler(Filters.text,handle_text))

    # handlers - error
    dp.add_error_handler(error)

    # -----------------------------------------------------------------------

    # start the Bot on Heroku
    #updater.start_polling() # terminal debugging
    updater.start_webhook(listen="0.0.0.0",port=int(PORT),url_path=TOKEN)
    updater.bot.setWebhook('https://regexo-bot.herokuapp.com/'+TOKEN)
    print('Bot started!')

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
	main()