import React, { useState, useEffect } from "react";
import { Menu, Plus } from "lucide-react";
import ChatPage from "./ChatPage";
import { motion, AnimatePresence } from "framer-motion";

export default function ChatLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [chats, setChats] = useState([]);
  const [activeChat, setActiveChat] = useState(null);

  const SIDEBAR_WIDTH = 240;

  useEffect(() => {
    loadChats();
  }, []);

  const loadChats = () => {
    setChats([
      { id: "1", title: "Flight to Mumbai", updated_at: new Date().toISOString() },
      { id: "2", title: "Baggage Inquiry", updated_at: new Date(Date.now() - 86400000).toISOString() },
      { id: "3", title: "Seat Selection Help", updated_at: new Date(Date.now() - 172800000).toISOString() }
    ]);
    setActiveChat("1");
  };

  const handleNewChat = () => {
    const newChat = {
      id: Date.now().toString(),
      title: "New Chat",
      updated_at: new Date().toISOString()
    };
    setChats([newChat, ...chats]);
    setActiveChat(newChat.id);
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="flex h-screen bg-[#f3f6ff] relative overflow-hidden">

      {/* OVERLAY (mobile) */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            className="fixed inset-0 bg-black/40 z-20 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* SIDEBAR */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.aside
            initial={{ x: -SIDEBAR_WIDTH }}
            animate={{ x: 0 }}
            exit={{ x: -SIDEBAR_WIDTH }}
            transition={{ type: "tween", duration: 0.25 }}
            className="fixed lg:static z-30 h-full bg-white shadow-xl border-r border-gray-200"
            style={{ width: SIDEBAR_WIDTH }}
          >
            {/* Sidebar Header */}
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold text-blue-900">Chats</h2>

              {/* Mobile close */}
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="lg:hidden p-2 rounded-md hover:bg-gray-100"
              >
                ✕
              </button>
            </div>

            {/* New Chat */}
            <div className="p-3">
              <button
                onClick={handleNewChat}
                className="w-full bg-blue-600 text-white flex items-center justify-center gap-2 py-2 rounded-lg shadow hover:bg-blue-700 transition"
              >
                <Plus size={18} /> New Chat
              </button>
            </div>

            {/* Chat List */}
            <div className="overflow-y-auto h-[calc(100%-110px)] p-3">
              {chats.map((chat) => (
                <div
                  key={chat.id}
                  onClick={() => setActiveChat(chat.id)}
                  className={`cursor-pointer px-3 py-3 rounded-lg border mb-2 transition-all ${
                    activeChat === chat.id
                      ? "bg-blue-50 border-blue-600 text-blue-700"
                      : "bg-white border-gray-200 hover:bg-gray-100"
                  }`}
                >
                  <div className="font-medium truncate">{chat.title}</div>
                  <div className="text-xs text-gray-500">{formatDate(chat.updated_at)}</div>
                </div>
              ))}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* MOBILE MENU BUTTON */}
      <button
        onClick={() => setIsSidebarOpen(true)}
        className="lg:hidden p-3 absolute top-4 left-4 bg-blue-600 text-white rounded-md shadow-md z-20"
      >
        <Menu size={22} />
      </button>

      {/* MAIN CHAT AREA */}
      <div className="flex-1 h-full overflow-hidden">
        <ChatPage />
      </div>
    </div>
  );
}
