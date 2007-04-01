import gtk
from logging import warn
import os, sys
import help_box
from gui import policy
from dialog import Dialog, MixedButton, frame
from zeroinstall.injector.model import network_levels
from zeroinstall.injector import trust, gpg
from freshness import freshness_levels, Freshness
from sets import Set

tips = gtk.Tooltips()

SHOW_CACHE = 0

class Preferences(Dialog):
	def __init__(self):
		Dialog.__init__(self)
		self.set_title('Zero Install Preferences')

		self.connect('destroy', lambda w: self.destroyed())

		content = gtk.VBox(False, 2)
		content.set_border_width(8)
		self.vbox.pack_start(content, True, True, 0)

		vbox = gtk.VBox(False, 0)
		frame(content, 'Policy settings', vbox)

		# Network use
		hbox = gtk.HBox(False, 2)
		vbox.pack_start(hbox, False, True, 0)
		hbox.set_border_width(4)

		eb = gtk.EventBox()	# For the tooltip
		network = gtk.combo_box_new_text()
		eb.add(network)
		for level in network_levels:
			network.append_text(level.capitalize())
		network.set_active(list(network_levels).index(policy.network_use))
		hbox.pack_start(gtk.Label('Network use:'), False, True, 0)
		hbox.pack_start(eb, True, True, 2)
		def set_network_use(combo):
			policy.network_use = network_levels[network.get_active()]
			policy.save_config()
			policy.recalculate()
		network.connect('changed', set_network_use)
		tips.set_tip(eb, _('This controls whether the injector will always try to '
			'run the best version, downloading it if needed, or whether it will prefer '
			'to run an older version that is already on your machine.'))

		hbox.show_all()

		# Freshness
		hbox = gtk.HBox(False, 2)
		vbox.pack_start(hbox, False, True, 0)
		hbox.set_border_width(4)

		times = [x.time for x in freshness_levels]
		if policy.freshness not in times:
			freshness_levels.append(Freshness(policy.freshness,
							  '%d seconds' % policy.freshness))
			times.append(policy.freshness)
		eb = gtk.EventBox()	# For the tooltip
		freshness = gtk.combo_box_new_text()
		eb.add(freshness)
		for level in freshness_levels:
			freshness.append_text(str(level))
		freshness.set_active(times.index(policy.freshness))
		hbox.pack_start(gtk.Label('Freshness:'), False, True, 0)
		hbox.pack_start(eb, True, True, 2)
		def set_freshness(combo):
			policy.freshness = freshness_levels[freshness.get_active()].time
			policy.save_config()
			policy.recalculate()
		freshness.connect('changed', set_freshness)
		tips.set_tip(eb, _('Sets how often the injector will check for new versions.'))

		stable_toggle = gtk.CheckButton('Help test new versions')
		vbox.pack_start(stable_toggle, False, True, 0)
		tips.set_tip(stable_toggle,
			"Try out new versions as soon as they are available, instead of "
			"waiting for them to be marked as 'stable'. "
			"This sets the default policy. Click on 'Interface Properties...' "
			"to set the policy for an individual interface.")
		stable_toggle.set_active(policy.help_with_testing)
		def toggle_stability(toggle):
			policy.help_with_testing = toggle.get_active()
			policy.save_config()
			policy.recalculate()
		stable_toggle.connect('toggled', toggle_stability)

		# Keys
		if hasattr(gpg, 'Key'):
			keys_area = KeyList()
		else:
			keys_area = gtk.Label('Sorry, this feature requires 0launch >= 0.27')
			keys_area.set_alignment(0, 0)
		frame(content, 'Security', keys_area, expand = True)

		# Responses

		self.add_button(gtk.STOCK_HELP, gtk.RESPONSE_HELP)
		self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)

		self.set_default_response(gtk.RESPONSE_CLOSE)
		self.default_widget.grab_focus()

		def response(dialog, resp):
			import download_box
			if resp in (gtk.RESPONSE_CLOSE, gtk.RESPONSE_DELETE_EVENT):
				self.destroy()
			elif resp == gtk.RESPONSE_HELP:
				gui_help.display()
		self.connect('response', response)

		self.set_default_size(-1, gtk.gdk.screen_height() / 3)
		self.vbox.show_all()

	def destroyed(self):
		global preferences_box
		preferences_box = None

class KeyList(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self, False, 0)

		label = gtk.Label('')
		label.set_markup('<i>You have said that you trust these keys to sign software updates.</i>')
		label.set_padding(4, 4)
		label.set_alignment(0, 0.5)
		self.pack_start(label, False, True, 0)

		self.trusted_keys = gtk.TreeStore(str, object)
		tv = gtk.TreeView(self.trusted_keys)
		tc = gtk.TreeViewColumn('Trusted keys', gtk.CellRendererText(), text = 0)
		tv.append_column(tc)
		swin = gtk.ScrolledWindow(None, None)
		swin.set_shadow_type(gtk.SHADOW_IN)
		swin.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
		swin.add(tv)
		trust.trust_db.ensure_uptodate()

		trust.trust_db.watchers.append(self.update_keys)
		self.connect('destroy', lambda w: trust.trust_db.watchers.remove(self.update_keys))

		self.pack_start(swin, True, True, 0)
		self.update_keys()

		def remove_key(fingerprint, domain):
			trust.trust_db.untrust_key(fingerprint, domain)
			trust.trust_db.notify()

		def trusted_keys_button_press(tv, bev):
			if bev.type == gtk.gdk.BUTTON_PRESS and bev.button == 3:
				pos = tv.get_path_at_pos(int(bev.x), int(bev.y))
				if not pos:
					return False
				path, col, x, y = pos
				if len(path) != 2:
					return False

				domain = self.trusted_keys[path[:-1]][0]
				key = self.trusted_keys[path][1]

				menu = gtk.Menu()

				item = gtk.MenuItem('Remove key for "%s"' % key.get_short_name())
				item.connect('activate',
					lambda item, fp = key.fingerprint, d = domain: remove_key(fp, d))
				item.show()
				menu.append(item)

				menu.popup(None, None, None, bev.button, bev.time)
				return True
			return False
		tv.connect('button-press-event', trusted_keys_button_press)

	def update_keys(self):
		self.trusted_keys.clear()
		domains = {}

		keys = gpg.load_keys(trust.trust_db.keys.keys())

		for fingerprint in keys:
			for domain in trust.trust_db.keys[fingerprint]:
				if domain not in domains:
					domains[domain] = Set()
				domains[domain].add(keys[fingerprint])
		for domain in domains:
			iter = self.trusted_keys.append(None, [domain, None])
			for key in domains[domain]:
				self.trusted_keys.append(iter, [key.name, key])

preferences_box = None
def show_preferences():
	global preferences_box
	if preferences_box is not None:
		preferences_box.present()
	else:
		preferences_box = Preferences()
		preferences_box.show()
		
gui_help = help_box.HelpBox("Zero Install Preferences Help",
('Overview', """

There are three ways to control which implementations are chosen. You can adjust the \
network policy and the overall stability policy, which affect all interfaces, or you \
can edit the policy of individual interfaces."""),

('Network use', """
The 'Network use' option controls how the injector uses the network. If off-line, \
the network is not used at all. If 'Minimal' is selected then the injector will use \
the network if needed, but only if it has no choice. It will run an out-of-date \
version rather than download a newer one. If 'Full' is selected, the injector won't \
worry about how much it downloads, but will always pick the version it thinks is best."""),

('Freshness', """
The feed files, which provide the information about which versions are \
available, are also cached. To update them, click on 'Refresh all now'. You can also \
get the injector to check for new versions automatically from time to time using \
the Freshness setting."""),

('Help test new versions', """
The overall stability policy can either be to prefer stable versions, or to help test \
new versions. Choose whichever suits you. Since different programmers have different \
ideas of what 'stable' means, you may wish to override this on a per-interface basis.

To set the policy for an interface individually, select it in the main window and \
click on 'Interface Properties'. See that dialog's help text for more information."""),

('Security', """
This section lists all keys which you currently trust. When fetching a new program or \
updates for an existing one, the feed must be signed by one of these keys. If not, \
you will be prompted to confirm that you trust the new key, and it will then be added \
to this list. To remove a key, right-click on it and choose 'Remove' from the menu."""),
)