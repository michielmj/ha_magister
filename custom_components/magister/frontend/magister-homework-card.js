/*!
 * Magister Homework planner card
 * Copyright (c) the ha_magister contributors. MIT License.
 * https://github.com/michielmj/ha_magister
 *
 * Includes Lit (lit, lit-html, lit-element and @lit/reactive-element), https://lit.dev
 *
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 3. Neither the name of the copyright holder nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=/* @__PURE__ */ new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:d,getOwnPropertyNames:ee,getOwnPropertySymbols:te,getPrototypeOf:ne}=Object,f=globalThis,p=f.trustedTypes,re=p?p.emptyScript:``,ie=f.reactiveElementPolyfillSupport,m=(e,t)=>e,h={toAttribute(e,t){switch(t){case Boolean:e=e?re:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},ae=(e,t)=>!l(e,t),g={attribute:!0,type:String,converter:h,reflect:!1,useDefault:!1,hasChanged:ae};Symbol.metadata??=Symbol(`metadata`),f.litPropertyMetadata??=/* @__PURE__ */ new WeakMap;var _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=g){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=d(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??g}static _$Ei(){if(this.hasOwnProperty(m(`elementProperties`)))return;let e=ne(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(m(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(m(`properties`))){let e=this.properties,t=[...ee(e),...te(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=/* @__PURE__ */ new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=/* @__PURE__ */ new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=/* @__PURE__ */ new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=/* @__PURE__ */ new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?h:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?h:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??ae)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=/* @__PURE__ */ new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=/* @__PURE__ */ new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=/* @__PURE__ */ new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:`open`},_[m(`elementProperties`)]=/* @__PURE__ */ new Map,_[m(`finalized`)]=/* @__PURE__ */ new Map,ie?.({ReactiveElement:_}),(f.reactiveElementVersions??=[]).push(`2.1.2`);var v=globalThis,y=e=>e,b=v.trustedTypes,x=b?b.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,S=`$lit$`,C=`lit$${Math.random().toFixed(9).slice(2)}$`,oe=`?`+C,se=`<${oe}>`,w=document,T=()=>w.createComment(``),E=e=>e===null||typeof e!=`object`&&typeof e!=`function`,D=Array.isArray,ce=e=>D(e)||typeof e?.[Symbol.iterator]==`function`,O=`[ 	
\f\r]`,k=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,A=/-->/g,j=/>/g,M=RegExp(`>|${O}(?:([^\\s"'>=/]+)(${O}*=${O}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),N=/'/g,P=/"/g,le=/^(?:script|style|textarea|title)$/i,F=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),I=Symbol.for(`lit-noChange`),L=Symbol.for(`lit-nothing`),R=/* @__PURE__ */ new WeakMap,z=w.createTreeWalker(w,129);function B(e,t){if(!D(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return x===void 0?t:x.createHTML(t)}var ue=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=k;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===k?c[1]===`!--`?o=A:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=M):(le.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=M):o=j:o===M?c[0]===`>`?(o=i??k,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?M:c[3]===`"`?P:N):o===P||o===N?o=M:o===A||o===j?o=k:(o=M,i=void 0);let d=o===M&&e[t+1].startsWith(`/>`)?` `:``;a+=o===k?n+se:l>=0?(r.push(s),n.slice(0,l)+S+n.slice(l)+C+d):n+C+(l===-2?t:d)}return[B(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},V=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=ue(t,n);if(this.el=e.createElement(l,r),z.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=z.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(S)){let t=u[o++],n=i.getAttribute(e).split(C),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?fe:r[1]===`?`?pe:r[1]===`@`?me:W}),i.removeAttribute(e)}else e.startsWith(C)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(le.test(i.tagName)){let e=i.textContent.split(C),t=e.length-1;if(t>0){i.textContent=b?b.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],T()),z.nextNode(),c.push({type:2,index:++a});i.append(e[t],T())}}}else if(i.nodeType===8){if(i.data===oe)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(C,e+1))!==-1;)c.push({type:7,index:a}),e+=C.length-1}}a++}}static createElement(e,t){let n=w.createElement(`template`);return n.innerHTML=e,n}};function H(e,t,n=e,r){if(t===I)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=E(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=H(e,i._$AS(e,t.values),i,r)),t}var de=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??w).importNode(t,!0);z.currentNode=r;let i=z.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new U(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new he(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=z.nextNode(),a++)}return z.currentNode=w,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},U=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=L,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=H(this,e,t),E(e)?e===L||e==null||e===``?(this._$AH!==L&&this._$AR(),this._$AH=L):e!==this._$AH&&e!==I&&this._(e):e._$litType$===void 0?e.nodeType===void 0?ce(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==L&&E(this._$AH)?this._$AA.nextSibling.data=e:this.T(w.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=V.createElement(B(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new de(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=R.get(e.strings);return t===void 0&&R.set(e.strings,t=new V(e)),t}k(t){D(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(T()),this.O(T()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=y(e).nextSibling;y(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},W=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=L,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(/* @__PURE__ */ new String),this.strings=n):this._$AH=L}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=H(this,e,t,0),a=!E(e)||e!==this._$AH&&e!==I,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=H(this,r[n+o],t,o),s===I&&(s=this._$AH[o]),a||=!E(s)||s!==this._$AH[o],s===L?e=L:e!==L&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===L?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},fe=class extends W{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===L?void 0:e}},pe=class extends W{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==L)}},me=class extends W{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=H(this,e,t,0)??L)===I)return;let n=this._$AH,r=e===L&&n!==L||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==L&&(n===L||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},he=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){H(this,e)}},ge=v.litHtmlPolyfillSupport;ge?.(V,U),(v.litHtmlVersions??=[]).push(`3.3.3`);var _e=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new U(t.insertBefore(T(),e),e,void 0,n??{})}return i._$AI(e),i},G=globalThis,K=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=_e(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return I}};K._$litElement$=!0,K.finalized=!0,G.litElementHydrateSupport?.({LitElement:K});var ve=G.litElementPolyfillSupport;ve?.({LitElement:K}),(G.litElementVersions??=[]).push(`4.2.2`);var q=[0,25,50,75,100];function J(e){return Number.isFinite(e)?Math.min(Math.round(Math.min(Math.max(e,0),100)/25)*25,100):0}function ye(e){if(!e.completed)return 100;let t=Math.round(e.last_partial);return Math.min(Math.max(Number.isFinite(t)?t:0,0),99)}var Y=/^(\d{4})-(\d{2})-(\d{2})$/;function X(e){let t=Y.exec(e);return t?new Date(Date.UTC(Number(t[1]),Number(t[2])-1,Number(t[3]))):/* @__PURE__ */ new Date(NaN)}function be(e,t){let n=X(e);return n.setUTCDate(n.getUTCDate()+t),n.toISOString().slice(0,10)}function xe(e,t){try{let n=new Intl.DateTimeFormat(`en-CA`,{timeZone:t,year:`numeric`,month:`2-digit`,day:`2-digit`}).format(e);if(Y.test(n))return n}catch{}return(/* @__PURE__ */ new Date(e.getTime()-e.getTimezoneOffset()*6e4)).toISOString().slice(0,10)}function Se(e,t){let n=X(e);return Number.isNaN(n.getTime())?e:new Intl.DateTimeFormat(t,{timeZone:`UTC`,weekday:`long`,day:`numeric`,month:`long`}).format(n)}function Ce(e,t){let n=be(t.today,t.daysAhead);return e.filter(e=>e.completed&&!t.showCompleted&&!t.keep?.has(e.uid)?!1:e.date<t.today?t.showPast:e.date<=n)}function we(e,t){return e<t?`past`:e===t?`today`:e===be(t,1)?`tomorrow`:`future`}function Te(e,t){let n=/* @__PURE__ */ new Map;for(let r of e){let e=n.get(r.date);e||(e={date:r.date,kind:we(r.date,t),items:[]},n.set(r.date,e)),e.items.push(r)}return[...n.values()].sort((e,t)=>e.date.localeCompare(t.date))}function Ee(e,t){let n=e.last_partial;return t<100?n=t:e.progress<100&&(n=e.progress),{progress:t,completed:t>=100,last_partial:n}}function De(e,t){return t.size===0?[...e]:e.map(e=>{let n=t.get(e.uid);return n?{...e,...n}:e})}var Z=[{period:`tomorrow`,option:`show_progress_tomorrow`},{period:`week`,option:`show_progress_week`},{period:`next_week`,option:`show_progress_next_week`}];function Oe(e){let t=Number.isFinite(e.value)?e.value:0;return Math.min(Math.max(Math.round(t),0),100)}function ke(e){if(!e||typeof e!=`object`)throw Error(`Invalid configuration`);let t=e.entity??``;if(typeof t!=`string`)throw Error(`entity must be a to-do entity id`);if(t!==``&&!t.startsWith(`todo.`))throw Error(`entity must be a to-do entity (todo.*)`);let n=e.days_ahead??7;if(typeof n!=`number`||!Number.isFinite(n)||n<0)throw Error(`days_ahead must be a number of days (0 or more)`);return{entity:t,show_completed:e.show_completed===!0,show_past:e.show_past===!0,days_ahead:Math.min(Math.floor(n),365),show_progress_tomorrow:e.show_progress_tomorrow===!0,show_progress_week:e.show_progress_week===!0,show_progress_next_week:e.show_progress_next_week===!0,title:typeof e.title==`string`?e.title:``}}var Ae={nl:{today:`Vandaag`,tomorrow:`Morgen`,earlier:`Eerder`,no_homework:`Geen huiswerk 🎉`,loading:`Laden…`,unavailable:`Magister is niet beschikbaar. Je ziet het laatst bekende huiswerk; wijzigen kan nu niet.`,offline:`Verbinding met Home Assistant verbroken. Opnieuw verbinden…`,choose_entity:`Kies een Magister-huiswerklijst in de kaartinstellingen.`,not_found:`Deze huiswerklijst is niet gevonden.`,unauthorized:`Je hebt geen toegang tot deze huiswerklijst.`,load_failed:`Het huiswerk kon niet worden geladen.`,save_failed:`Opslaan mislukt. De wijziging is teruggedraaid.`,save_unauthorized:`Geen rechten om voortgang te wijzigen.`,dismiss:`Sluiten`,cancelled:`Les vervallen`,attachments:`Bijlagen in Magister`,lesson_hour:`Uur {n}`,mark_done:`Markeer {subject} als klaar`,mark_open:`Markeer {subject} als niet klaar`,progress_of:`Voortgang van {subject}`,percent:`{n} %`,expand:`Toon de volledige tekst`,collapse:`Toon minder`,progress_label:{tomorrow:`Morgen`,week:`Deze week`,next_week:`Volgende week`},progress_done:`{completed} van {items} klaar`,progress_empty:`geen huiswerk`,progress_unavailable:`niet beschikbaar`,type:{1:`Huiswerk`,2:`Proefwerk`,3:`Tentamen`,4:`SO`,5:`MO`},editor:{entity:`Huiswerklijst (to-do van een kind)`,title:`Titel (optioneel)`,show_completed:`Toon afgerond huiswerk`,show_past:`Toon eerdere dagen`,days_ahead:`Dagen vooruit`,show_progress_tomorrow:`Toon voortgang van morgen`,show_progress_week:`Toon voortgang van deze week`,show_progress_next_week:`Toon voortgang van volgende week`}},en:{today:`Today`,tomorrow:`Tomorrow`,earlier:`Earlier`,no_homework:`No homework`,loading:`Loading…`,unavailable:`Magister is not available. You see the last known homework; changes are not possible now.`,offline:`Connection to Home Assistant lost. Reconnecting…`,choose_entity:`Choose a Magister homework list in the card settings.`,not_found:`This homework list was not found.`,unauthorized:`You have no access to this homework list.`,load_failed:`The homework could not be loaded.`,save_failed:`Saving failed. The change was rolled back.`,save_unauthorized:`No permission to change progress.`,dismiss:`Dismiss`,cancelled:`Lesson cancelled`,attachments:`Attachments in Magister`,lesson_hour:`Period {n}`,mark_done:`Mark {subject} as done`,mark_open:`Mark {subject} as not done`,progress_of:`Progress of {subject}`,percent:`{n}%`,expand:`Show the full text`,collapse:`Show less`,progress_label:{tomorrow:`Tomorrow`,week:`This week`,next_week:`Next week`},progress_done:`{completed} of {items} done`,progress_empty:`no homework`,progress_unavailable:`not available`,type:{1:`Homework`,2:`Test`,3:`Exam`,4:`Short test`,5:`Oral test`},editor:{entity:`Homework list (a child's to-do)`,title:`Title (optional)`,show_completed:`Show completed homework`,show_past:`Show earlier days`,days_ahead:`Days ahead`,show_progress_tomorrow:`Show progress for tomorrow`,show_progress_week:`Show progress for this week`,show_progress_next_week:`Show progress for next week`}}};function je(e){return e?.toLowerCase().startsWith(`nl`)?`nl`:`en`}function Me(e){return Ae[je(e)]}function Q(e,t){return e.replace(/\{(\w+)\}/g,(e,n)=>n in t?String(t[n]):e)}function Ne(e,t,n){return e.type[t]??n}function Pe(){return[{name:`entity`,required:!0,selector:{entity:{filter:{domain:`todo`,integration:`magister`}}}},{name:`title`,selector:{text:{}}},{name:`show_completed`,selector:{boolean:{}}},{name:`show_past`,selector:{boolean:{}}},{name:`days_ahead`,selector:{number:{min:0,max:365,step:1,mode:`box`}}},...Z.map(({option:e})=>({name:e,selector:{boolean:{}}}))]}function Fe(e){return{entity:e.entity??``,title:e.title??``,show_completed:e.show_completed??!1,show_past:e.show_past??!1,days_ahead:e.days_ahead??7,show_progress_tomorrow:e.show_progress_tomorrow??!1,show_progress_week:e.show_progress_week??!1,show_progress_next_week:e.show_progress_next_week??!1}}function Ie(e,t){let n={...e,type:e.type??`custom:magister-homework-card`,entity:typeof t.entity==`string`?t.entity:e.entity??``},r=t.title;typeof r==`string`&&r.trim()!==``?n.title=r:delete n.title,t.show_completed===!0?n.show_completed=!0:delete n.show_completed,t.show_past===!0?n.show_past=!0:delete n.show_past;let i=n;for(let{option:e}of Z)t[e]===!0?i[e]=!0:delete i[e];let a=t.days_ahead,o=a===``||a==null?NaN:Number(a);return Number.isFinite(o)&&o>=0&&o!==7?n.days_ahead=Math.min(Math.floor(o),365):delete n.days_ahead,n}var Le=class extends K{constructor(...e){super(...e),this._computeLabel=e=>this._texts().editor[e.name]??e.name,this._valueChanged=e=>{if(e.stopPropagation(),!this._config)return;let t=Ie(this._config,e.detail.value);this._config=t,this.dispatchEvent(new CustomEvent(`config-changed`,{detail:{config:t},bubbles:!0,composed:!0}))}}static{this.properties={hass:{attribute:!1},_config:{state:!0}}}setConfig(e){this._config=e}_texts(){return Me(this.hass?.locale?.language??this.hass?.language)}render(){return this._config?F`<ha-form
      .hass=${this.hass}
      .data=${Fe(this._config)}
      .schema=${Pe()}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`:L}},Re=`magister/homework/subscribe`,ze=`magister/homework/set_progress`,Be=6e3,$=3e4,Ve=6e5,He=`M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z`;function Ue(e){try{Promise.resolve(e()).catch(()=>void 0)}catch{}}var We=class extends K{static{this.properties={_payload:{state:!0},_loadError:{state:!0},_offline:{state:!0},_overlay:{state:!0},_expanded:{state:!0},_toast:{state:!0}}}constructor(){super(),this._subscribedEntity=``,this._generation=0,this._tokens=/* @__PURE__ */ new Map,this._nextToken=0,this._retryDelay=$,this._hassKey=``,this._shownDay=``,this._touched=/* @__PURE__ */ new Set,this._onDisconnected=()=>{this._offline=!0},this._onReady=()=>{this._offline=!1,this._loadError&&this._retry()},this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._toast=``}static getConfigElement(){return document.createElement(`magister-homework-card-editor`)}static getStubConfig(e){return{entity:Object.entries(e?.entities??{}).find(([e,t])=>e.startsWith(`todo.`)&&t?.platform===`magister`)?.[0]??``}}setConfig(e){let t=ke(e);t.entity!==this._config?.entity&&(this._resetSubscription(),this._payload=void 0,this._loadError=void 0,this._offline=!1,this._overlay=/* @__PURE__ */ new Map,this._expanded=/* @__PURE__ */ new Set,this._tokens.clear(),this._touched.clear(),this._retryDelay=$),this._config=t,this.requestUpdate(),this._ensureSubscription()}set hass(e){this._hass=e;let t=`${e?.locale?.language??``}|${e?.language??``}|${e?.config?.time_zone??``}`;t===this._hassKey&&this._payload||(this._hassKey=t,this.requestUpdate()),this._ensureSubscription()}get hass(){return this._hass}getCardSize(){let e=this._visibleItems().length;return e===0?3:2+e*2}getGridOptions(){return{columns:12,min_columns:6,min_rows:3}}connectedCallback(){super.connectedCallback(),this._ensureSubscription(),this._dayTimer=setInterval(()=>{this._currentDay()!==this._shownDay&&this.requestUpdate()},6e4)}disconnectedCallback(){super.disconnectedCallback(),this._resetSubscription(),this._toastTimer&&clearTimeout(this._toastTimer),this._dayTimer&&clearInterval(this._dayTimer),this._dayTimer=void 0}_ensureSubscription(){let e=this._hass,t=this._config?.entity;if(!this.isConnected||!e?.connection||!t||this._subscribedEntity===t&&this._connection===e.connection)return;this._resetSubscription(),this._attach(e.connection),this._subscribedEntity=t;let n=++this._generation;e.connection.subscribeMessage(e=>{n===this._generation&&this._onPayload(e)},{type:Re,entity_id:t},{resubscribe:!0}).then(e=>{n===this._generation?this._unsubscribe=e:Ue(e)},e=>{if(n!==this._generation)return;let t=e?.code;this._loadError=t===`not_found`||t===`invalid_format`?`not_found`:t===`unauthorized`?`unauthorized`:`load_failed`,this._scheduleRetry()})}_scheduleRetry(){this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=setTimeout(()=>{this._retryTimer=void 0,this._retry()},this._retryDelay),this._retryDelay=Math.min(this._retryDelay*2,Ve)}_retry(){this._resetSubscription(),this._ensureSubscription()}_attach(e){e.addEventListener?.(`disconnected`,this._onDisconnected),e.addEventListener?.(`ready`,this._onReady),this._connection=e,e.connected===!1&&(this._offline=!0)}_resetSubscription(){this._generation++,this._unsubscribe&&Ue(this._unsubscribe),this._unsubscribe=void 0,this._retryTimer&&clearTimeout(this._retryTimer),this._retryTimer=void 0,this._connection?.removeEventListener?.(`disconnected`,this._onDisconnected),this._connection?.removeEventListener?.(`ready`,this._onReady),this._connection=void 0,this._subscribedEntity=``}_onPayload(e){this._payload=e,this._loadError=void 0,this._retryDelay=$,this._offline=!1;let t=/* @__PURE__ */ new Map;for(let[e,n]of this._overlay)this._tokens.has(e)&&t.set(e,n);this._overlay=t}async _setProgress(e,t){let n=this._hass,r=this._config?.entity,i=this._payload?.items.find(t=>t.uid===e);if(!n||!r||!i||!this._payload?.available||this._offline)return;let a=++this._nextToken;this._tokens.set(e,a),t>=100&&this._touched.add(e);let o=Ee(De([i],this._overlay)[0]??i,t);this._overlay=new Map(this._overlay).set(e,o);try{let i=await n.callWS({type:ze,entity_id:r,item:e,progress:t});if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let s=this._payload.items.find(t=>t.uid===e),c=new Map(this._overlay);s?.progress===i.progress?c.delete(e):c.set(e,{...o,progress:i.progress,completed:i.completed}),this._overlay=c}catch(t){if(this._tokens.get(e)!==a)return;this._tokens.delete(e);let n=new Map(this._overlay);n.delete(e),this._overlay=n;let r=t?.code,i=this._texts();this._showToast(r===`unauthorized`?i.save_unauthorized:i.save_failed)}}_showToast(e){this._toast=e,this._toastTimer&&clearTimeout(this._toastTimer),this._toastTimer=setTimeout(()=>{this._toast=``},Be)}_toggleExpanded(e){let t=new Set(this._expanded);t.delete(e)||t.add(e),this._expanded=t}_language(){return this._hass?.locale?.language??this._hass?.language??`en`}_texts(){return Me(this._language())}_currentDay(){return xe(/* @__PURE__ */ new Date,this._hass?.config?.time_zone)}_today(){return this._shownDay=this._currentDay(),this._shownDay}_visibleItems(){let e=this._config;return!e||!this._payload?[]:Ce(De(this._payload.items,this._overlay),{showCompleted:e.show_completed,showPast:e.show_past,daysAhead:e.days_ahead,today:this._today(),keep:this._touched})}_dayTitle(e,t){return e.kind===`today`?t.today:e.kind===`tomorrow`?t.tomorrow:Se(e.date,je(this._language())===`nl`?`nl`:`en-GB`)}render(){let e=this._config,t=this._texts();return F`<ha-card .header=${e?.title??``}>
      <div class="content ${e?.title?`titled`:``}">${this._renderBody(t)}</div>
      ${this._toast?F`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${()=>{this._toast=``}}>${t.dismiss}</button>
          </div>`:L}
    </ha-card>`}_renderBody(e){if(!this._config?.entity)return F`<p class="state">${e.choose_entity}</p>`;if(this._loadError)return F`<p class="state error">${e[this._loadError]}</p>`;if(!this._payload)return F`<p class="state">${e.loading}</p>`;let t=this._payload.available,n=t&&!this._offline,r=Te(this._visibleItems(),this._today()),i=F`${this._renderBars(e)}${t?L:F`<p class="banner" role="status">${e.unavailable}</p>`}${this._offline?F`<p class="banner" role="status">${e.offline}</p>`:L}`;if(r.length===0)return t?F`${i}<p class="state empty">${e.no_homework}</p>`:F`${i}`;let a=r.findIndex(e=>e.kind===`past`);return F`${i}<div class="days ${t?``:`stale`}">
        ${r.map((t,r)=>F`
            ${r===a?F`<h3 class="section">${e.earlier}</h3>`:L}
            <section class="day" aria-labelledby="day-${t.date}">
              <h4 id="day-${t.date}" class=${t.kind}>${this._dayTitle(t,e)}</h4>
              <ul>
                ${t.items.map(t=>this._renderItem(t,e,n))}
              </ul>
            </section>
          `)}
      </div>`}_renderBars(e){let t=this._config,n=this._payload?.progress,r=Z.filter(({option:e})=>t?.[e]);return r.length===0?L:F`<div class="bars">
      ${r.map(({period:t})=>{let r=e.progress_label[t],i=n?.[t]??null;if(!i)return F`<div class="bar unavailable">
            <div class="bar-head"><span>${r}</span></div>
            <div
              class="track"
              role="progressbar"
              aria-label=${r}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuetext=${e.progress_unavailable}
            ></div>
            <div class="bar-note">${e.progress_unavailable}</div>
          </div>`;let a=Oe(i),o=Q(e.percent,{n:a}),s=i.items===0?e.progress_empty:Q(e.progress_done,{completed:i.completed,items:i.items});return F`<div class="bar">
          <div class="bar-head"><span>${r}</span><span class="bar-value">${o}</span></div>
          <div
            class="track"
            role="progressbar"
            aria-label=${r}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow=${a}
            aria-valuetext="${o}, ${s}"
          >
            <div class="fill" style="width: ${a}%"></div>
          </div>
          <div class="bar-note">${s}</div>
        </div>`})}
    </div>`}_renderItem(e,t,n){let r=this._expanded.has(e.uid),i=Ne(t,e.info_type,e.label);return F`<li class=${[`item`,e.is_test?`test`:``,e.completed?`done`:``,e.cancelled?`cancelled`:``].filter(Boolean).join(` `)}>
      <input
        type="checkbox"
        .checked=${e.completed}
        ?disabled=${!n}
        aria-label=${Q(e.completed?t.mark_open:t.mark_done,{subject:e.subject})}
        @change=${()=>void this._setProgress(e.uid,ye(e))}
      />
      <div class="main">
        <div class="head">
          <span class="chip ${e.is_test?`test`:``}">${i}</span>
          <span class="subject">${e.subject}</span>
          ${e.lesson_hour===null?L:F`<span class="meta">${Q(t.lesson_hour,{n:e.lesson_hour})}</span>`}
          ${e.cancelled?F`<span class="badge">${t.cancelled}</span>`:L}
          ${e.has_attachments?F`<span class="meta attachments" title=${t.attachments}
                ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${He}></path></svg
                ><span class="sr-only">${t.attachments}</span></span
              >`:L}
        </div>
        ${e.text?F`<button
              type="button"
              class="text ${r?`expanded`:``}"
              aria-expanded=${r?`true`:`false`}
              title=${r?t.collapse:t.expand}
              @click=${()=>{this._toggleExpanded(e.uid)}}
            >${e.text}</button>`:L}
        ${this._renderProgress(e,t,n)}
      </div>
    </li>`}_renderProgress(e,t,n){let r=J(e.progress),i=q.includes(e.progress);return F`<div class="progress">
      <div
        class="segments"
        role="radiogroup"
        aria-label=${Q(t.progress_of,{subject:e.subject})}
      >
        ${q.map(a=>F`<button
            type="button"
            role="radio"
            class="segment ${a===r?`selected`:``} ${a<r?`below`:``} ${i?``:`between`}"
            aria-checked=${i&&a===r?`true`:`false`}
            aria-label=${Q(t.percent,{n:a})}
            tabindex=${a===r?0:-1}
            ?disabled=${!n}
            @click=${()=>{a!==e.progress&&this._setProgress(e.uid,a)}}
            @keydown=${t=>{this._onSegmentKey(t,e.uid,e.progress)}}
          >
            ${a}
          </button>`)}
      </div>
      <span class="percent">${Q(t.percent,{n:e.progress})}</span>
    </div>`}_onSegmentKey(e,t,n){let r=q.indexOf(J(n)),i;switch(e.key){case`ArrowRight`:case`ArrowDown`:i=Math.min(r+1,q.length-1);break;case`ArrowLeft`:case`ArrowUp`:i=Math.max(r-1,0);break;case`Home`:i=0;break;case`End`:i=q.length-1;break;default:return}e.preventDefault();let a=q[i];if(a===void 0||a===n)return;let o=e.currentTarget;this._setProgress(t,a),this.updateComplete.then(()=>{o.parentElement?.querySelector(`[tabindex="0"]`)?.focus()})}static{this.styles=o`
    :host {
      display: block;
    }
    ha-card {
      display: block;
      overflow: hidden;
    }
    .content {
      padding: 0 16px 16px;
    }
    .content:not(.titled) {
      padding-top: 12px;
    }
    .state {
      margin: 16px 0;
      text-align: center;
      color: var(--secondary-text-color);
    }
    .state.error {
      color: var(--error-color);
    }
    .state.empty {
      font-size: 1.1em;
      padding: 12px 0;
    }
    .banner {
      margin: 0 0 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      color: var(--primary-text-color);
      font-size: 0.9em;
    }
    .bars {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0 0 12px;
    }
    .titled .bars {
      margin-top: 12px;
    }
    .bar-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 0.9em;
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .bar-value {
      font-variant-numeric: tabular-nums;
    }
    .track {
      height: 8px;
      margin: 4px 0 2px;
      border-radius: 4px;
      overflow: hidden;
      background: var(--divider-color);
    }
    .fill {
      height: 100%;
      border-radius: 4px;
      background: var(--primary-color);
    }
    .bar-note {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .bar.unavailable .bar-head {
      color: var(--secondary-text-color);
    }
    .days.stale {
      opacity: 0.55;
    }
    h3.section {
      margin: 16px 0 0;
      font-size: 0.85em;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--secondary-text-color);
    }
    h4 {
      margin: 16px 0 4px;
      font-size: 1em;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    h4::first-letter {
      text-transform: uppercase;
    }
    h4.today {
      color: var(--primary-color);
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .item {
      display: flex;
      gap: 12px;
      padding: 10px 0 10px 8px;
      border-top: 1px solid var(--divider-color);
      border-left: 3px solid transparent;
    }
    .item:first-child {
      border-top: none;
    }
    .item.test {
      border-left-color: var(--warning-color, #ffa600);
      background: color-mix(in srgb, var(--warning-color, #ffa600) 8%, transparent);
    }
    .item.done .subject,
    .item.done .text {
      color: var(--secondary-text-color);
      text-decoration: line-through;
    }
    input[type="checkbox"] {
      flex: none;
      width: 22px;
      height: 22px;
      margin: 2px 0 0;
      accent-color: var(--primary-color);
      cursor: pointer;
    }
    input[type="checkbox"]:disabled {
      cursor: default;
    }
    .main {
      flex: 1;
      min-width: 0;
    }
    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 8px;
    }
    .subject {
      font-weight: 500;
      color: var(--primary-text-color);
      overflow-wrap: anywhere;
    }
    .item.test .subject {
      font-weight: 700;
    }
    .chip {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      border: 1px solid var(--divider-color);
    }
    .chip.test {
      font-weight: 700;
      color: var(--text-primary-color, #fff);
      background: var(--warning-color, #ffa600);
      border-color: var(--warning-color, #ffa600);
    }
    .meta {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .attachments svg {
      width: 16px;
      height: 16px;
      vertical-align: middle;
      fill: currentColor;
    }
    .badge {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      color: var(--error-color);
      border: 1px solid var(--error-color);
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
    .text {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      overflow: hidden;
      width: 100%;
      margin: 4px 0 0;
      padding: 0;
      border: none;
      background: none;
      font: inherit;
      font-size: 0.9em;
      text-align: left;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--secondary-text-color);
      cursor: pointer;
    }
    .text.expanded {
      display: block;
      -webkit-line-clamp: unset;
      line-clamp: unset;
      overflow: visible;
    }
    .progress {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
    }
    .segments {
      display: flex;
      flex: 0 1 260px;
      min-width: 0;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      overflow: hidden;
    }
    .segment {
      flex: 1;
      min-width: 0;
      min-height: 36px;
      padding: 0;
      border: none;
      border-left: 1px solid var(--divider-color);
      background: transparent;
      color: var(--secondary-text-color);
      font: inherit;
      font-size: 0.8em;
      cursor: pointer;
    }
    .segment:first-child {
      border-left: none;
    }
    .segment.below {
      background: color-mix(in srgb, var(--primary-color) 22%, transparent);
    }
    .segment.between.selected {
      background: color-mix(in srgb, var(--primary-color) 55%, transparent);
    }
    .segment.selected {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      font-weight: 700;
    }
    .segment:disabled {
      cursor: default;
    }
    .segment:focus-visible,
    .text:focus-visible,
    input[type="checkbox"]:focus-visible,
    .toast button:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .percent {
      font-size: 0.8em;
      min-width: 3.2em;
      color: var(--secondary-text-color);
    }
    .toast {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin: 0 16px 16px;
      padding: 8px 12px;
      border-radius: 8px;
      background: var(--error-color);
      color: var(--text-primary-color, #fff);
      font-size: 0.9em;
    }
    .toast button {
      border: none;
      background: none;
      color: inherit;
      font: inherit;
      font-weight: 700;
      text-decoration: underline;
      cursor: pointer;
    }
    @media (max-width: 480px) {
      .segments {
        flex: 1 1 auto;
      }
      .segment {
        min-height: 40px;
      }
    }
  `}};customElements.get(`magister-homework-card`)||customElements.define(`magister-homework-card`,We),customElements.get(`magister-homework-card-editor`)||customElements.define(`magister-homework-card-editor`,Le),window.customCards=window.customCards??[],window.customCards.some(e=>e.type===`magister-homework-card`)||window.customCards.push({type:`magister-homework-card`,name:`Magister Homework planner`,description:`Homework and tests of one child from Magister, with progress per item. / Huiswerk en toetsen van één kind uit Magister, met voortgang per onderdeel.`,preview:!0,documentationURL:`https://github.com/michielmj/ha_magister`});export{We as MagisterHomeworkCard,Le as MagisterHomeworkCardEditor};