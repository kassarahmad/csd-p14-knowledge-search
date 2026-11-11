const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
test('una partita completa arriva a un milione con 15 domande valide', () => {
  assert.ok(fs.existsSync(__dirname + '/game.js'), 'Manca il motore del quiz');
  const { Game, questions, prizes } = require('./game.js');
  assert.equal(questions.length, 15);
  assert.equal(prizes.length, 15);
  const game = new Game();
  for (const q of questions) {
    assert.equal(q.answers.length, 4);
    assert.ok(q.correct >= 0 && q.correct < 4);
    game.answer(q.correct);
  }
  assert.equal(game.status, 'won');
  assert.equal(game.winnings, 1000000);
});
test('errore e ritiro rispettano i traguardi e bloccano ulteriori risposte', () => {
  const {Game, questions} = require('./game.js');
  const lost = new Game();
  for(let i=0;i<5;i++) lost.answer(questions[i].correct);
  lost.answer((questions[5].correct+1)%4);
  assert.equal(lost.winnings,1000);
  assert.equal(lost.status,'lost');
  const early = new Game();
  early.answer(questions[0].correct);
  early.answer((questions[1].correct+1)%4);
  assert.equal(early.winnings,0);
  const retired = new Game();
  retired.answer(questions[0].correct);
  retired.retire();
  retired.answer(questions[1].correct);
  assert.equal(retired.winnings,100);
  assert.equal(retired.status,'retired');
});
