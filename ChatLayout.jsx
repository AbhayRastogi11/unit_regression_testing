// src/components/ChatLayout.jsx
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
      { id: "1", title: "Baggage Issue", updated_at: new Date().toISOString() },
      { id: "2", title: "Flight Reschedule", updated_at: new Date().toISOString() },
    ]);
    setActiveChat("1");
  };

  const handleNewChat = () => {
    const newChat = {
      id: Date.now().toString(),
      title: "New Chat",
      updated_at: new Date().toISOString(),
    };
    setChats([newChat, ...chats]);
    setActiveChat(newChat.id);
  };

  const formatChatDate = (dateString) => {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

    return date.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    });
  };

  return (
    <div className="flex h-screen bg-[#f8faff] relative overflow-hidden">

      {/* BACKDROP OVERLAY */}
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
            transition={{ type: "tween", duration: 0.27 }}
            className="fixed lg:static z-30 h-full bg-white shadow-xl border-r border-gray-200"
            style={{ width: SIDEBAR_WIDTH }}
          >
            <div className="p-4 border-b flex justify-between items-center">
              <h2 className="text-lg font-semibold text-[#1e3a8a]">Chats</h2>
              <button
                onClick={handleNewChat}
                className="p-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition"
              >
                <Plus size={18} />
              </button>
            </div>

            <div className="overflow-y-auto h-full p-2">
              {chats.length === 0 ? (
                <p className="text-gray-400 text-center mt-10">No chats yet</p>
              ) : (
                chats.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => setActiveChat(chat.id)}
                    className={`cursor-pointer px-3 py-3 rounded-lg border mb-2 transition-all ${
                      activeChat === chat.id
                        ? "bg-blue-50 border-blue-500 text-blue-700 shadow-sm"
                        : "bg-white border-gray-200 hover:bg-gray-100"
                    }`}
                  >
                    <div className="font-medium">{chat.title}</div>
                    <div className="text-xs text-gray-500">
                      {formatChatDate(chat.updated_at)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* TOP BAR (only mobile) */}
      <div className="lg:hidden p-3 absolute top-0 left-0 z-10">
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 bg-blue-600 text-white rounded-md shadow-md"
        >
          <Menu size={22} />
        </button>
      </div>

      {/* MAIN CHAT AREA */}
      <div className="flex-1 h-full overflow-hidden">
        <ChatPage />
      </div>
    </div>
  );
}
