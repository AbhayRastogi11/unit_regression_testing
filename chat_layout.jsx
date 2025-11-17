import { useState, useEffect } from 'react';
import { Menu, Plus, MessageSquare, X } from 'lucide-react';
import ChatPage from './ChatPage';

interface Chat {
  id: string;
  title: string;
  updated_at: string;
}

export default function ChatLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChat, setActiveChat] = useState<string | null>(null);

  useEffect(() => {
    loadChats();
  }, []);

  const loadChats = async () => {
    setChats([
      {
        id: '1',
        title: 'Flight to Mumbai',
        updated_at: new Date().toISOString(),
      },
      {
        id: '2',
        title: 'Baggage Inquiry',
        updated_at: new Date(Date.now() - 86400000).toISOString(),
      },
      {
        id: '3',
        title: 'Seat Selection Help',
        updated_at: new Date(Date.now() - 172800000).toISOString(),
      },
    ]);
  };

  const handleNewChat = () => {
    const newChat: Chat = {
      id: Date.now().toString(),
      title: 'New Chat',
      updated_at: new Date().toISOString(),
    };
    setChats([newChat, ...chats]);
    setActiveChat(newChat.id);
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday';
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <div
        className={`bg-white border-r border-gray-200 transition-all duration-300 flex flex-col ${
          isSidebarOpen ? 'w-80' : 'w-0'
        }`}
      >
        {isSidebarOpen && (
          <div className="flex-1 flex flex-col h-full">
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-800">Chats</h2>
                <button
                  onClick={() => setIsSidebarOpen(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors lg:hidden"
                >
                  <X className="w-5 h-5 text-gray-600" />
                </button>
              </div>
              <button
                onClick={handleNewChat}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
              >
                <Plus className="w-5 h-5" />
                New Chat
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {chats.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full px-4 text-center">
                  <MessageSquare className="w-12 h-12 text-gray-300 mb-3" />
                  <p className="text-gray-500 text-sm">No chats yet</p>
                  <p className="text-gray-400 text-xs mt-1">Start a new conversation</p>
                </div>
              ) : (
                <div className="py-2">
                  {chats.map((chat) => (
                    <button
                      key={chat.id}
                      onClick={() => setActiveChat(chat.id)}
                      className={`w-full px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors border-l-4 ${
                        activeChat === chat.id
                          ? 'bg-blue-50 border-blue-600'
                          : 'border-transparent'
                      }`}
                    >
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                        <MessageSquare className="w-5 h-5 text-blue-600" />
                      </div>
                      <div className="flex-1 text-left min-w-0">
                        <div className="font-medium text-gray-800 truncate">{chat.title}</div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {formatDate(chat.updated_at)}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col relative">
        {!isSidebarOpen && (
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="absolute top-4 left-4 z-10 p-2 bg-white hover:bg-gray-50 border border-gray-200 rounded-lg shadow-sm transition-colors"
          >
            <Menu className="w-6 h-6 text-gray-600" />
          </button>
        )}

        <div className={`flex-1 ${!isSidebarOpen ? '' : ''}`}>
          <ChatPage chatId={activeChat} onNewMessage={loadChats} />
        </div>
      </div>
    </div>
  );
}
