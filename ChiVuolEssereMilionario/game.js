(function (root) {
  'use strict';
  const prizes = [100,200,300,500,1000,2000,4000,8000,16000,32000,64000,125000,250000,500000,1000000];
  const questions = [
    ['Qual è la capitale d’Italia?', ['Roma','Milano','Torino','Napoli'],0],
    ['Quanti lati ha un triangolo?', ['Quattro','Cinque','Tre','Sei'],2],
    ['Quale pianeta è detto il pianeta rosso?', ['Venere','Marte','Giove','Saturno'],1],
    ['Chi ha scritto la Divina Commedia?', ['Manzoni','Petrarca','Boccaccio','Dante Alighieri'],3],
    ['Quale oceano è il più esteso?', ['Atlantico','Indiano','Pacifico','Artico'],2],
    ['Qual è il simbolo chimico dell’oro?', ['Ag','Au','Fe','O'],1],
    ['In quale anno l’uomo mise piede sulla Luna per la prima volta?', ['1969','1959','1979','1961'],0],
    ['Chi dipinse Guernica?', ['Dalí','Monet','Van Gogh','Picasso'],3],
    ['Quale organello svolge la fotosintesi nelle cellule vegetali?', ['Mitocondrio','Cloroplasto','Ribosoma','Lisosoma'],1],
    ['Quale città ospita la sede della Corte internazionale di giustizia?', ['Ginevra','Bruxelles','L’Aia','Strasburgo'],2],
    ['Quale numero è primo?', ['91','87','97','93'],2],
    ['Chi compose Le quattro stagioni?', ['Vivaldi','Bach','Mozart','Verdi'],0],
    ['Quale elemento ha numero atomico 74?', ['Osmio','Tungsteno','Rutenio','Tantalio'],1],
    ['Quale trattato del 1648 pose fine alla guerra dei Trent’anni?', ['Utrecht','Versailles','Tordesillas','Pace di Vestfalia'],3],
    ['Qual è l’unità SI della capacità elettrica?', ['Henry','Weber','Farad','Tesla'],2]
  ].map(([text, answers, correct]) => ({text, answers, correct}));
  class Game {
    constructor() { this.index = 0; this.winnings = 0; this.status = 'playing'; }
    retire() { if (this.status === 'playing') this.status = 'retired'; }
    answer(choice) {
      if (this.status !== 'playing') return;
      if (choice !== questions[this.index].correct) { this.winnings = this.index >= 10 ? prizes[9] : this.index >= 5 ? prizes[4] : 0; this.status = 'lost'; return; }
      this.winnings = prizes[this.index++];
      if (this.index === questions.length) this.status = 'won';
    }
  }
  const api = {Game, questions, prizes};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Quiz = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
