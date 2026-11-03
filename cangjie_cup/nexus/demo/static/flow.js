(function(root){
  'use strict';
  class DemoFlow {
    constructor(){this.reset();}
    reset(){this.stage=-1;this.status='READY';this.running=false;return this;}
    start(){if(this.status==='READY'||this.status==='PAUSED'){this.running=true;this.status='RUNNING';}return this;}
    pause(){if(this.running){this.running=false;this.status='PAUSED';}return this;}
    tick(denied=false){
      if(!this.running)return this;
      this.stage=Math.min(this.stage+1,5);
      if(denied&&this.stage===3){this.running=false;this.status='DENIED';}
      else if(this.stage===5){this.running=false;this.status='REVIEW_PENDING';}
      return this;
    }
    accept(){if(this.status==='REVIEW_PENDING'){this.stage=6;this.status='DELIVERED';this.running=false;}return this;}
    reject(){if(this.status==='REVIEW_PENDING'){this.status='REJECTED';this.running=false;}return this;}
  }
  if(typeof module!=='undefined')module.exports={DemoFlow};
  root.DemoFlow=DemoFlow;
})(typeof globalThis!=='undefined'?globalThis:this);
