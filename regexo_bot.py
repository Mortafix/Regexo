import logging
import os
from telegram import ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, PicklePersistence
from emoji import emojize
from datetime import date
from re import match


# Enable logging and port
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
logger = logging.getLogger(__name__)
PORT = int(os.environ.get('PORT', 5000))
# Config variables
TOKEN = '1178476105:AAEeuMbyRQ5blEM11V0xtqEkiMsDGhnikyU'
ADD_TEST,NEW_TEST,REGEX_END,ADD_DESCRIPTION,DATE_CHOOSE = range(5)

#--------------------------------- Functions ------------------------------------------

def date_to_key(date_key=None):
	date_key =  date.today() if not date_key else date.fromisoformat('-'.join(date_key.split('-')[::-1]))
	return '{:04d}{:02d}{:02d}'.format(date_key.year,date_key.month,date_key.day)

def em(emoji_string):
	return emojize(':'+emoji_string+':',use_aliases=True)

REGEX = dict()

#--------------------------------- Utilities ------------------------------------------

def error(update, context):
    '''Log errors caused by updates.'''
    logger.warning('Update "%s" caused error "%s"', update, context.error)

#--------------------------------- Simple commands ------------------------------------

def start(update, context):
    '''Send start message. [command /start]'''
    user = update.message.from_user
    update.message.reply_text('Welcome {}! !\nI\'m `Regexo, your worst regular expression nightmare.'.format(user.first_name),parse_mode='Markdown')

def help(update, context):
    '''Send help message. [command /help]'''
    update.message.reply_text('{} Non posso aiutarti, non ne hai bisogno..'.format(emojize(':raised_hand:',use_aliases=True)))

def cancel(update, context):
    '''User cancel conversation, exit gently'''
    user = update.message.from_user
    update.message.reply_text('Perchè mi abbandoni *{}*? {}'.format(user.first_name,em('sob')),parse_mode='Markdown')
    return ConversationHandler.END

#--------------------------------- Handler --------------------------------------------

def handle_text(update, context):
	'''Handler for a non-command message.'''
	update.message.reply_text('{} Hey *{}*, non sembra un comado accettabile questo...'.format(em('x'),update.message.from_user.first_name),parse_mode='Markdown')

# ADD REGEX (admin) ---------------------------------

def new_regex(update,context):
	'''/newregex - Choose date'''
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Today',callback_data='date-today'),InlineKeyboardButton(text='Another Date',callback_data='date-another')]])
	update.message.reply_text('{} Choose challenge *date*.'.format(em('date')),reply_markup=reply_keyboard,parse_mode='Markdown')
	return DATE_CHOOSE

def date_dispatcher(update,context):
	'''/newregex - Date'''
	telegram_id = update.callback_query.message.chat.id
	query = update.callback_query
	query.answer()
	if query.data == 'date-today':
		query.edit_message_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
		context.user_data.update({telegram_id:{'regex-date':date_to_key()}})
		return ADD_TEST
	elif query.data == 'date-another': query.edit_message_text('Insert *date*.\n\[dd-mm-yyyy]',parse_mode='Markdown'); return ADD_DESCRIPTION

def add_description(update,context):
	'''/newregex - Add description'''
	telegram_id = update.message.chat.id
	date = update.message.text
	try: date_key = date_to_key(date)
	except ValueError: update.message.reply_text('{} Wrong date!\n\nTry again.\n\[dd-mm-yyyy]'.format(em('x')),parse_mode='Markdown'); return ADD_DESCRIPTION
	context.user_data.update({telegram_id:{'regex-date':date_to_key(date)}})
	update.message.reply_text('{} Insert *description*.\n(markdown available)'.format(em('page_facing_up')),parse_mode='Markdown')
	return ADD_TEST

def add_test(update,context):
	'''/newregex - Choose a new test or stop'''
	telegram_id = update.message.chat.id
	msg = ''
	reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text='Add test',callback_data='test-new'),InlineKeyboardButton(text='End',callback_data='test-stop')]])
	d_key = context.user_data.get(telegram_id).get('regex-date')
	if d_key not in REGEX: REGEX[d_key] = (update.message.text,[])
	else:
		test = tuple(update.message.text.split('\n'))
		if len(test) != 2: msg = '{} Wrong test format!\n'.format(em('x'))
		else: REGEX.update({d_key:(REGEX[d_key][0],REGEX[d_key][1]+[test])}); msg = '{} Great! You added a new test!\n'.format(em('white_check_mark'))
	print(REGEX)
	update.message.reply_text(msg+'Do you want to add a new *test*?',reply_markup=reply_keyboard,parse_mode='Markdown')
	return NEW_TEST

def new_test(update,context):
	'''/newregex - Add test'''
	query = update.callback_query
	query.answer()
	reply_keyboard = InlineKeyboardMarkup(	[[InlineKeyboardButton(text='Preview',callback_data='regex-preview'),InlineKeyboardButton(text='Publish',callback_data='regex-publish')],
											[InlineKeyboardButton(text='Modify',callback_data='regex-modify'),InlineKeyboardButton(text='Remove',callback_data='regex_remove')]])
	if query.data == 'test-new': query.edit_message_text('{} Add new *test*.\n\nLine 1: `Test string`\nLine 2: `Answer`'.format(em('floppy_disk')),parse_mode='Markdown'); return ADD_TEST
	elif query.data == 'test-stop': query.edit_message_text('{} Challenge complete!'.format(em('tada')),reply_markup=reply_keyboard,parse_mode='Markdown'); return REGEX_END

def complete_challenge(update,context):
	'''/newregex - Regex complete'''
	query = update.callback_query
	query.answer()
	query.edit_message_text('Ho clicacato su {}'.format(query.data))
	print(REGEX)
	return ConversationHandler.END

# MAIN ----------------------------------------------------------------------------------

def main():
    '''Bot instance'''
    pp = PicklePersistence(filename='regexo_persistence')
    updater = Updater(TOKEN, persistence=pp, use_context=True)
    dp = updater.dispatcher

    # -----------------------------------------------------------------------
 
    # commands
    cmd_start = CommandHandler("start", start)
    cmd_help = CommandHandler("help", help)

    # conversations
    conv_new_regex = ConversationHandler(
    	entry_points = [CommandHandler('newregex',new_regex)],
    	states = {
    		ADD_DESCRIPTION: [MessageHandler(Filters.text,add_description)],
    		ADD_TEST: [MessageHandler(Filters.text,add_test)],
    		DATE_CHOOSE: [CallbackQueryHandler(date_dispatcher)],
    		NEW_TEST: [CallbackQueryHandler(new_test)],
    		REGEX_END: [CallbackQueryHandler(complete_challenge)]
    	},
    	fallbacks=[CommandHandler('cancel',cancel)],
    	name='login-conversation',
    	persistent=True
    	)

    # -----------------------------------------------------------------------

    # handlers - commands and conversations
    dp.add_handler(conv_new_regex)
    dp.add_handler(cmd_start)
    dp.add_handler(cmd_help)

    # handlers - no command
    dp.add_handler(MessageHandler(Filters.text,handle_text))

    # handlers - error
    dp.add_error_handler(error)

    # -----------------------------------------------------------------------

    # start the Bot on Heroku
    updater.start_polling() # terminal debugging
    #updater.start_webhook(listen="0.0.0.0",port=int(PORT),url_path=TOKEN)
    #updater.bot.setWebhook('https://telegram-ecobot.herokuapp.com/'+TOKEN)
    print('Bot started!')

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
	main()