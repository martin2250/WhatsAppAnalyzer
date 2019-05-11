#!/usr/bin/python
from dataclasses import dataclass, field
from pathlib import Path
import datetime
import re
import collections
import emoji
import typing
import argparse

parser = argparse.ArgumentParser(description='analyze exported whatsapp chat')
parser.add_argument('files', nargs = '+', type=Path, help='txt files')
parser.add_argument('--daily', action='store_true')
parser.add_argument('--hourly', action='store_true')
args = parser.parse_args()

# ---------------------------------------------------------------------------- #

@dataclass
class Message:
	time: datetime
	sender_id: int
	text: str

@dataclass
class Chat:
	messages: list = field(default_factory=list)
	sender_ids: list = field(default_factory=list)

@dataclass
class Sender:
	sender_id: int
	name: str

# ---------------------------------------------------------------------------- #
senders_by_id = []
senders_by_name = {}


re_datematch = re.compile('^(\d+\/\d+\/\d+, \d+:\d+)')
re_datenamematch = re.compile('^(\d+\/\d+\/\d+, \d+:\d+) - ([^:]+): (.*)$')

def parse_chat(path):
	global senders_by_id, senders_by_name

	chat = Chat()

	with path.open() as f:
		for line in f:
			line = line.strip()

			if not re_datematch.match(line):
				if len(chat.messages) > 0:
					chat.messages[-1].text += line
			else:
				match = re_datenamematch.match(line)

				if not match:
					# print(f'failed to match {line}')
					continue

				time = match.group(1)
				name = match.group(2)
				text = match.group(3)

				if not name in senders_by_name:
					sender = Sender(len(senders_by_id), name)
					senders_by_id.append(sender)
					senders_by_name[name] = sender

				sender_id = senders_by_name[name].sender_id

				if not sender_id in chat.sender_ids:
					chat.sender_ids.append(sender_id)

				chat.messages.append(Message(
					datetime.datetime.strptime(time, '%m/%d/%y, %H:%M'),
					sender_id,
					text
				))

	return chat

# ---------------------------------------------------------------------------- #

# chat_paths = list(Path('chats').glob('*.txt'))
chats = [parse_chat(path) for path in args.files]

# ---------------------------------------------------------------------------- #

@dataclass
class Statistic:
	message_count: int = 0
	message_length: int = 0
	word_count: int = 0
	emoji_count: int = 0
	emoji_stat: dict = field(default_factory=dict)

StatisticIndex = collections.namedtuple('StatisticIndex', ['sender_id', 'chat_id'])

# ---------------------------------------------------------------------------- #
# collect total, daily and hourly statistics
statistics_by_date = {}
statistics_by_hour = {}
statistics = {}

for chat_id, chat in enumerate(chats):
	for message in chat.messages:
		index = StatisticIndex(sender_id = message.sender_id, chat_id = chat_id)
		date = message.time.date()
		hour = message.time.hour

		if not index in statistics:
			statistics[index] = Statistic()

		if not index in statistics_by_date:
			statistics_by_date[index] = {}

		if not index in statistics_by_hour:
			statistics_by_hour[index] = {}

		if not date in statistics_by_date[index]:
			statistics_by_date[index][date] = Statistic()

		if not hour in statistics_by_hour[index]:
			statistics_by_hour[index][hour] = Statistic()

		for stat in [statistics_by_date[index][date], statistics_by_hour[index][hour], statistics[index]]:
			stat.message_count += 1
			stat.message_length += len(message.text)
			stat.word_count += len(message.text.split())

		for find_item in emoji.emoji_lis(message.text):
			emoji_type = find_item['emoji']

			for stat in [statistics_by_date[index][date], statistics_by_hour[index][hour], statistics[index]]:
				stat.emoji_count += 1

			if emoji_type in statistics[index].emoji_stat:
				statistics[index].emoji_stat[emoji_type] += 1
			else:
				statistics[index].emoji_stat[emoji_type] = 1

# ---------------------------------------------------------------------------- #
# print total statistics
for chat_id, chat in enumerate(chats):
	print('-' * 50)
	for sender_id in chat.sender_ids:
		index = StatisticIndex(sender_id = sender_id, chat_id = chat_id)
		stat = statistics[index]
		stat_by_date = statistics_by_date[index]

		first_date, *_, last_date = statistics_by_date[index].keys()
		total_days = (last_date - first_date).days

		print(senders_by_id[sender_id].name)

		print(f'# of messages | total: {stat.message_count} avg (day): {stat.message_count/total_days:0.1f}')
		print(f'letters       | total: {stat.message_length} avg (message): {stat.message_length/stat.message_count:0.1f}')
		print(f'words         | total: {stat.word_count} avg (message): {stat.word_count/stat.message_count:0.1f}')
		print(f'emoji         | total: {stat.emoji_count} avg (message): {stat.emoji_count/stat.message_count:0.1f}')
		print(f'word length   | avg: {stat.message_length/stat.word_count:0.1f}')

		emojis = list(stat.emoji_stat.items())
		emojis.sort(key=lambda i:i[1], reverse=True)
		emojis = emojis[:10]

		print('most used emojis:')
		for emoji_type, emoji_count in emojis:
			print(f'{emoji_type}: {emoji_count} ({100.0 * emoji_count/stat.emoji_count:0.2f}%)')


print('-' * 50)

# ---------------------------------------------------------------------------- #
# create daily and hourly plots
import matplotlib.pyplot as plt
import matplotlib.dates
import numpy as np

statistics_to_plot = []
if args.hourly:
	statistics_to_plot.append(statistics_by_hour)
if args.daily:
	statistics_to_plot.append(statistics_by_date)

for statistics_by_index in statistics_to_plot:
	for chat_id, chat in enumerate(chats):
		fig, axes = plt.subplots(nrows = len(chat.sender_ids), sharex=True)

		for sender_id, ax in zip(chat.sender_ids, axes):

			ax.set_title(senders_by_id[sender_id].name)

			index_stat = StatisticIndex(sender_id = sender_id, chat_id = chat_id)

			dates = list(statistics_by_index[index_stat].keys())
			stats = list(statistics_by_index[index_stat].values())

			message_counts = [stat.message_count for stat in stats]
			word_counts = [stat.word_count for stat in stats]
			message_lengths = [stat.message_length for stat in stats]
			emoji_counts = [stat.emoji_count for stat in stats]

			ax.bar(dates, message_counts, label='message count')
			# ax.bar(dates, word_counts, label='word count')
			# ax.bar(dates, message_lengths, label='message length')
			# ax.bar(dates, emoji_counts, label='emoji count')

			ax.legend()
plt.show()
