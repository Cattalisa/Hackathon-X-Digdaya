import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * RightPanel Component
 * 
 * Contains the Nusa AI Chatbot interface and Quick Links.
 * Handles the actual API communication to the chat endpoint.
 */
interface RightPanelProps {
  selectedSymbol?: string;
  chatInput: string;
  setChatInput: (val: string) => void;
}

export const RightPanel: React.FC<RightPanelProps> = ({ selectedSymbol, chatInput, setChatInput }) => {
  
  const initialMessage = { 
    role: 'assistant', 
    content: `Nusa AI siap membantu analisis komprehensif untuk **seluruh saham perbankan** di bursa. Apa yang ingin Anda diskusikan?` 
  };
  
  const [messages, setMessages] = useState<any[]>([initialMessage]);
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || loading) return;
    
    const userMsg = chatInput.trim();
    setChatInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userMsg
        })
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response || 'No response.' }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Koneksi ke AI Agent gagal.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4 }}
      className="p-[14px] flex flex-col gap-[14px] overflow-y-auto"
    >
      
      {/* Chat Head */}
      <div className="flex items-center gap-[7px] text-[12px] font-semibold text-[#eef2ee]">
        <span className="w-[7px] h-[7px] rounded-full bg-[#22e07a] shadow-[0_0_8px_rgba(34,224,122,0.35)]"></span> 
        NUSA CHATBOT AI
      </div>

      {/* Chat Box */}
      <div className="bg-[#10151199] border border-[#1e2621] rounded-[10px] p-[12px] flex flex-col gap-[10px] flex-1">
        <AnimatePresence>
          {messages.map((msg, i) => {
            if (msg.role === 'assistant') {
              return (
                <motion.div 
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  key={i} 
                  className="text-[11.5px] leading-[1.5] p-[9px_11px] rounded-[10px] max-w-[92%] bg-[#12181388] border border-[#1e2621] text-[#8a958c] rounded-bl-[2px]"
                >
                  <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                  {msg.source && <span className="text-[#5b655d] text-[10px] ml-1 block mt-1">Source: {msg.source}</span>}
                </motion.div>
              );
            } else {
              return (
                <motion.div 
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  key={i} 
                  className="text-[11.5px] leading-[1.5] p-[9px_11px] rounded-[10px] max-w-[92%] bg-[rgba(34,224,122,0.12)] border border-[#1a7a48] text-[#eef2ee] self-end rounded-br-[2px]"
                >
                  {msg.content}
                </motion.div>
              );
            }
          })}
        </AnimatePresence>
        {loading && (
          <div className="text-[11.5px] leading-[1.5] p-[9px_11px] rounded-[10px] max-w-[92%] bg-[#12181388] border border-[#1e2621] text-[#8a958c] rounded-bl-[2px] animate-pulse">
            Thinking...
          </div>
        )}
      </div>

      {/* Chat Input */}
      <form onSubmit={handleSend} className="flex items-center gap-[8px] bg-[#0d1210] border border-[#1e2621] rounded-[8px] p-[8px_10px] mt-[2px]">
        <input 
          type="text" 
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          placeholder="Tanya Nusa AI..." 
          className="flex-1 bg-transparent border-none outline-none text-[#eef2ee] text-[11.5px]"
        />
        <button type="submit" className="w-[26px] h-[26px] rounded-[6px] bg-[#22e07a] border-none flex items-center justify-center cursor-pointer shrink-0 disabled:opacity-50" disabled={loading || !chatInput.trim()}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#04150a" strokeWidth="2.5"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
        </button>
      </form>
    </motion.div>
  );
};
