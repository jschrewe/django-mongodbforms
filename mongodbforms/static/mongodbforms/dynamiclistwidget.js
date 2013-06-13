(function(context) {
	window.mdbf = {}
	/* by @k33g_org */
	var root = this;

	(function(speculoos) {

		var Class = (function() {
			function Class(definition) {
				/* from CoffeeScript */
				var __hasProp = Object.prototype.hasOwnProperty, m, F;

				this["extends"] = function(child, parent) {
					for (m in parent) {
						if (__hasProp.call(parent, m))
							child[m] = parent[m];
					}
					function ctor() {
						this.constructor = child;
					}
					ctor.prototype = parent.prototype;
					child.prototype = new ctor;
					child.__super__ = child["super"] = parent.prototype;
					return child;
				}

				if (definition.constructor.name === "Object") {
					F = function() {
					};
				} else {
					F = definition.constructor;
				}

				/* inheritance */
				if (definition["extends"]) {
					this["extends"](F, definition["extends"])
				}
				for (m in definition) {
					if (m != 'constructor' && m != 'extends') {
						if (m[0] != '$') {
							F.prototype[m] = definition[m];
						} else { /* static members */
							F[m.split('$')[1]] = definition[m];
						}
					}
				}

				return F;
			}
			return Class;
		})();

		speculoos.Class = Class;

	})(mdbf);

	/*
	 * ! onDomReady.js 1.2 (c) 2012 Tubal Martin - MIT license
	 */
	!function(definition) {
		if (typeof define === "function" && define.amd) {
			// Register as an AMD module.
			define(definition);
		} else {
			// Browser globals
			window.mdbf.onDomReady = definition();
		}
	}
	(function() {

		'use strict';

		var win = window, doc = win.document, docElem = doc.documentElement,

		FALSE = false, COMPLETE = "complete", READYSTATE = "readyState", ATTACHEVENT = "attachEvent", ADDEVENTLISTENER = "addEventListener", DOMCONTENTLOADED = "DOMContentLoaded", ONREADYSTATECHANGE = "onreadystatechange",

		// W3C Event model
		w3c = ADDEVENTLISTENER in doc, top = FALSE,

		// isReady: Is the DOM ready to be used? Set to true once it
		// occurs.
		isReady = FALSE,

		// Callbacks pending execution until DOM is ready
		callbacks = [];

		// Handle when the DOM is ready
		function ready(fn) {
			if (!isReady) {

				// Make sure body exists, at least, in case IE gets a
				// little overzealous (ticket #5443).
				if (!doc.body) {
					return defer(ready);
				}

				// Remember that the DOM is ready
				isReady = true;

				// Execute all callbacks
				while (fn = callbacks.shift()) {
					defer(fn);
				}
			}
		}

		// The document ready event handler
		function DOMContentLoadedHandler() {
			if (w3c) {
				doc.removeEventListener(DOMCONTENTLOADED,
						DOMContentLoadedHandler, FALSE);
				ready();
			} else if (doc[READYSTATE] === COMPLETE) {
				// we're here because readyState === "complete" in oldIE
				// which is good enough for us to call the dom ready!
				doc.detachEvent(ONREADYSTATECHANGE,
						DOMContentLoadedHandler);
				ready();
			}
		}

		// Defers a function, scheduling it to run after the current
		// call stack has cleared.
		function defer(fn, wait) {
			// Allow 0 to be passed
			setTimeout(fn, +wait >= 0 ? wait : 1);
		}

		// Attach the listeners:

		// Catch cases where onDomReady is called after the browser
		// event has already occurred.
		// we once tried to use readyState "interactive" here, but it
		// caused issues like the one
		// discovered by ChrisS here:
		// http://bugs.jquery.com/ticket/12282#comment:15
		if (doc[READYSTATE] === COMPLETE) {
			// Handle it asynchronously to allow scripts the opportunity
			// to delay ready
			defer(ready);

			// Standards-based browsers support DOMContentLoaded
		} else if (w3c) {
			// Use the handy event callback
			doc[ADDEVENTLISTENER](DOMCONTENTLOADED,
					DOMContentLoadedHandler, FALSE);

			// A fallback to window.onload, that will always work
			win[ADDEVENTLISTENER]("load", ready, FALSE);

			// If IE event model is used
		} else {
			// ensure firing before onload,
			// maybe late but safe also for iframes
			doc[ATTACHEVENT](ONREADYSTATECHANGE,
					DOMContentLoadedHandler);

			// A fallback to window.onload, that will always work
			win[ATTACHEVENT]("onload", ready);

			// If IE and not a frame
			// continually check to see if the document is ready
			try {
				top = win.frameElement == null && docElem;
			} catch (e) {
			}

			if (top && top.doScroll) {
				(function doScrollCheck() {
					if (!isReady) {
						try {
							// Use the trick by Diego Perini
							// http://javascript.nwbox.com/IEContentLoaded/
							top.doScroll("left");
						} catch (e) {
							return defer(doScrollCheck, 50);
						}

						// and execute any waiting functions
						ready();
					}
				})();
			}
		}

		function onDomReady(fn) {
			// If DOM is ready, execute the function (async), otherwise
			// wait
			isReady ? defer(fn) : callbacks.push(fn);
		}

		// Add version
		onDomReady.version = "1.2";

		return onDomReady;
	});
	/*
	 * nut, the concise CSS selector engine
	 * 
	 * Version : 0.2.0 Author : Aurélien Delogu (dev@dreamysource.fr) Homepage :
	 * https://github.com/pyrsmk/nut License : MIT
	 */

	window.mdbf.nut = function() {

		var doc = document, firstChild = 'firstChild', nextSibling = 'nextSibling', getElementsByClassName = 'getElementsByClassName', length = 'length',

		/*
		 * Get id node
		 * 
		 * Parameters String selector : one selector Object context : one
		 * context
		 * 
		 * Return Array : nodes
		 */
		getNodesFromIdSelector = function(selector, context) {
			var node = doc.getElementById(selector);
			if (!node) {
				return [];
			} else {
				return [ node ];
			}
		},

		/*
		 * Get nodes corresponding to one class name (for IE<9)
		 * 
		 * Parameters String selector : one selector Object context : one
		 * context
		 * 
		 * Return Array : nodes
		 */
		getNodesByClassName = function(name, context) {
			// Init vars
			var node = context[firstChild], nodes = [], elements;
			// Browse children
			if (node) {
				do {
					if (node.nodeType == 1) {
						// Match the class
						if (node.className
								&& node.className.match('\\b' + name + '\\b')) {
							nodes.push(node);
						}
						// Get nodes from node's children
						if ((elements = getNodesByClassName(name, node))[length]) {
							nodes = nodes.concat(elements);
						}
					}
				} while (node = node[nextSibling]);
			}
			return nodes;
		},

		/*
		 * Get nodes from a class selector
		 * 
		 * Parameters String selector : one selector Object context : one
		 * context
		 * 
		 * Return Array : nodes
		 */
		getNodesFromClassSelector = function(selector, context) {
			if (context[getElementsByClassName]) {
				return context[getElementsByClassName](selector);
			} else {
				return getNodesByClassName(selector, context);
			}
		},

		/*
		 * Get nodes from a tag selector
		 * 
		 * Parameters String selector : one selector Object context : one
		 * context
		 * 
		 * Return Array : nodes
		 */
		getNodesFromTagSelector = function(selector, context) {
			return context.getElementsByTagName(selector);
		};

		/*
		 * Select DOM nodes
		 * 
		 * Parameters String selectors : CSS selectors Array, Object context :
		 * contextual node
		 * 
		 * Return Array : found nodes
		 */
		return function(selectors, context) {
			// Format
			if (!context) {
				context = doc;
			}
			if (typeof context == 'object' && context.pop) {
				context = context[0];
			}
			// Init vars
			var local_contexts, future_local_contexts, selector, elements, nodes = [], j, k, l, m, n, o, getNodesFromSelector;
			// Prepare selectors
			selectors = selectors.split(',');
			n = -1;
			while (selector = selectors[++n]) {
				selectors[n] = selector.split(/\s+/);
			}
			// Evaluate selectors for each global context
			j = selectors[length];
			while (j) {
				// Init local context
				local_contexts = [ context ];
				// Evaluate selectors
				k = -1;
				l = selectors[--j][length];
				while (++k < l) {
					// Drop empty selectors
					if (selector = selectors[j][k]) {
						// Id
						if (selector.charAt(0) == '#') {
							selector = selector.substr(1);
							getNodesFromSelector = getNodesFromIdSelector;
						}
						// Class
						else if (selector.charAt(0) == '.') {
							selector = selector.substr(1);
							getNodesFromSelector = getNodesFromClassSelector;
						}
						// Tag
						else {
							getNodesFromSelector = getNodesFromTagSelector;
						}
						// Evaluate current selector for each local context
						future_local_contexts = [];
						m = -1;
						while (local_contexts[++m]) {
							elements = getNodesFromSelector(selector,
									local_contexts[m]);
							n = -1;
							o = elements[length];
							while (++n < o) {
								future_local_contexts.push(elements[n]);
							}
						}
						// Set new local contexts
						local_contexts = future_local_contexts;
					}
				}
				// Append new nodes
				nodes = nodes.concat(local_contexts);
			}
			return nodes;
		};

	}();

	window.mdbf.FieldClass = mdbf.Class({
		constructor: function FieldClass(class_name) {
			// name of the field. used to generate additional fields
			this.name = class_name.split('-')[1];
			this.context = mdbf.nut('.' + class_name);
			this.inputs = mdbf.nut('input', context);
			// contains the max number in use for the inputs id and name
			this.input_counter = this.inputs.length - 1;
			// base to add more fields on click
			this.empty_input = this.inputs[0].cloneNode(true);
			this.empty_input.value = '';
			this.empty_input.id = '';
			this.empty_input.name = '';
			console.log(this.inputs);
		},
	});
	
	window.mdbf.init = function(class_name) {
		var field = mdbf.FieldClass(class_name);
	}
}());
