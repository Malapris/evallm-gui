from lib.llm_search import wwwsearch, get_web_content, askllm


if __name__ == '__main__':
    
    systemprompt = 'Tu es un assistant qui répond à des questions sur les animaux.'
    prompt = 'Qui sont les palmipèdes noctunes ?'
    response = askllm(systemprompt, prompt)
    print(response)
    print('########################################################')
    exit()
    
    results = wwwsearch('les palmipèdes noctunes')
    print(results)
    print('########################################################')
    context = get_web_content(results)
    print(context)
    print('########################################################')
    