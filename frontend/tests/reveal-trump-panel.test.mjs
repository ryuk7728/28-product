import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire, Module } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const filename = fileURLToPath(new URL('../src/components/panels/RevealTrumpPanel.tsx', import.meta.url));
const result = await build({
  entryPoints: [filename], bundle: true, write: false,
  platform: 'node', format: 'cjs', jsx: 'automatic',
  external: ['react', 'react/*'], loader: { '.scss': 'empty' },
});
const compiled = new Module(filename);
compiled.paths = createRequire(filename).resolve.paths('react');
compiled._compile(result.outputFiles[0].text, filename);
const { RevealTrumpPanel } = compiled.exports;

function render(names, seats = [0, 1, 2, 3]) {
  return renderToStaticMarkup(React.createElement(RevealTrumpPanel, {
    onReveal() {}, onKeepHidden() {},
    getPlayerName: seat => names[seat], currentSuit: 'Spades',
    playedCards: seats.map(seatIndex => ({ seatIndex, cardId: 'Spades_Jack' })),
  }));
}

test('reveal dialog labels every card with its actual room player name', () => {
  const html = render(['Maya', 'Arjun', 'Zoya', 'pranay'], [2, 0, 3, 1]);
  const labels = [...html.matchAll(/class="player-name">([^<]+):<\/span>/g)].map(match => match[1]);
  assert.deepEqual(labels, ['Zoya', 'Maya', 'pranay', 'Arjun']);
  assert.doesNotMatch(html, /T-1000|Skynet|Partner/);
  assert.match(html, /Reveal Trump/);
  assert.match(html, /Keep Hidden/);
});

test('updated player names are reflected and safely escaped', () => {
  assert.match(render(['New & Name', 'Arjun', 'Zoya', 'pranay'], [0]), /New &amp; Name:/);
  assert.doesNotMatch(render(['New name', 'Arjun', 'Zoya', 'pranay'], [0]), /Maya|T-1000/);
});

test('empty trick does not render stale player labels', () => {
  assert.doesNotMatch(render(['Maya', 'Arjun', 'Zoya', 'pranay'], []), /player-name|played-cards-section/);
});
