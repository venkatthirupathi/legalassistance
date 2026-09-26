const $ = (selector) => document.querySelector(selector)
const doc = $('#document')
const second = $('#second-document')
const question = $('#question')
const errorBox = $('#error')
const results = $('#results')
const output = $('#output')
let task = 'overview'
let lastResult = ''

const sample = `INDEPENDENT DESIGN SERVICES AGREEMENT\n\nThis Agreement is made on September 26, 2026 between Northline Studio (Client) and Rowan Vale (Designer). The Designer will deliver a visual identity and website concepts by November 21, 2026.\n\nPAYMENT. Client will pay a fixed fee of $8,750 within 60 days after final delivery and acceptance. Client alone determines whether work is acceptable. No deposit is required.\n\nINTELLECTUAL PROPERTY. Upon creation, Designer assigns to Client all rights in the work, drafts, concepts, methods, and tools used or developed during the engagement, whether or not included in the final work.\n\nTERMINATION. Client may terminate at any time without cause. Designer may terminate only after a material breach remains uncured for 30 days. Upon termination, Designer will return all payments received and provide all work completed.\n\nINDEMNITY. Designer will defend and indemnify Client against any claims, losses, expenses, and attorneys' fees arising from the services, without limitation.\n\nCONFIDENTIALITY. Designer will keep all Client information confidential indefinitely.\n\nGOVERNING LAW. This Agreement is governed by the laws of Delaware. Any dispute must be brought exclusively in Wilmington, Delaware.`

function escapeHtml(value) { return value.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])) }
function markdown(value) {
  let html = escapeHtml(value)
    .replace(/^### (.+)$/gm, '<h3>$1</h3>').replace(/^## (.+)$/gm, '<h2>$1</h2>').replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(?:<li>.*<\/li>\n?)+/g, match => `<ul>${match}</ul>`)
  return html.split(/\n{2,}/).map(block => /^<(h|ul)/.test(block) ? block : `<p>${block.replace(/\n/g, '<br>')}</p>`).join('')
}
function updateCount(){ $('#count').textContent = `${doc.value.length.toLocaleString()} / 70,000` }
function showError(message){ errorBox.textContent = message; errorBox.hidden = false }

doc.addEventListener('input', updateCount)
$('#file').addEventListener('change', async (event) => {
  const file = event.target.files[0]
  if (!file) return
  if (file.size > 250000) return showError('That file is too large. Add a plain-text file under 250 KB.')
  doc.value = await file.text(); updateCount(); errorBox.hidden = true
})
$('#sample').addEventListener('click', () => { doc.value = sample; updateCount(); errorBox.hidden = true })
document.querySelectorAll('.lens').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.lens').forEach(item => item.classList.remove('selected'))
  button.classList.add('selected'); task = button.dataset.task
  $('#question-field').hidden = task !== 'question'; $('#compare-field').hidden = task !== 'compare'
}))

$('#analyze').addEventListener('click', async () => {
  errorBox.hidden = true
  if (doc.value.trim().length < 80) return showError('Add at least a paragraph of document text before analyzing.')
  if (task === 'question' && !question.value.trim()) return showError('Enter a question about the document.')
  if (task === 'compare' && second.value.trim().length < 80) return showError('Add the second document before comparing.')
  const button = $('#analyze'); button.disabled = true
  results.hidden = false; $('#loading').hidden = false; output.innerHTML = ''; results.scrollIntoView({behavior:'smooth'})
  try {
    const response = await fetch('/api/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({task, document:doc.value, secondDocument:second.value, question:question.value}) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'The analysis could not be completed.')
    lastResult = data.result; output.innerHTML = markdown(lastResult)
  } catch (error) { results.hidden = true; showError(error.message) }
  finally { $('#loading').hidden = true; button.disabled = false }
})
$('#copy').addEventListener('click', async () => { if(lastResult){ await navigator.clipboard.writeText(lastResult); $('#copy').textContent='Copied'; setTimeout(()=>$('#copy').textContent='Copy',1400) } })
$('#download').addEventListener('click', () => { if(!lastResult)return; const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([lastResult],{type:'text/plain'})); a.download='clauseshield-findings.txt'; a.click(); URL.revokeObjectURL(a.href) })
