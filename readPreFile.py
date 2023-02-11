import requests
from bs4 import BeautifulSoup
import time


#サーバ上のXMLファイルをキャッシュする
class XMLDataGetter() :

        def __init__(self):
                self.data_cache = {}

        def get(self, data_path):


                soup = None

                if data_path in self.data_cache :

                        soup = self.data_cache[data_path]


                elif data_path.startswith('http') :

                        soup = self.get_from_html_path(data_path)

                else :

                        soup = self.get_from_local_path(data_path)

                return soup


        def get_from_html_path(self, url):

                r = requests.get(url)
                soup = BeautifulSoup(r.content, 'xml')
                r.close()

                time.sleep(1.0)

                self.data_cache[url] = soup

                return soup

        def get_from_local_path(self, local_path):


                fin = open(local_path, 'rb')
                bdata = fin.read()
                soup = BeautifulSoup(bdata, 'xml')
                fin.close()


                self.data_cache[local_path] = soup

                return soup



#表示リンクベースファイルのツリー構造
class YuhoStructureTree():

	def __init__(self, file_path, xml_data_getter):



		#データの読み込みに成功しようがどうだろうがルートだけは用意しておく
		self.root_node = YuhoStructureNode('document_root', 'root')
		self.root_node.set_href('root')


		#木構造巡回のための復帰情報を詰んでおくためのスタック
		#通常はルートから巡回を開始する
		self.init_walking_status() 


		soup = xml_data_getter.get(file_path)


		#親子関係読み込み後のhref取得に用いる
		roleRef_elems = soup.select('roleRef')
		loc_elems = soup.select('loc')	


		#まずはリンク構造(親子関係)を読み込み木構造を生成する


		#presentationLinkごとに構造を取得する
		document_number = 0
		for primary_item in soup.select('presentationLink'):

			document_number = document_number + 1

			#大項目の名称を取得
			primary_item_name = primary_item.get('xlink:role')
			sub_root_node = YuhoStructureNode(primary_item_name, 'document_name')

			#大項目のhref属性を設定
			for elem in roleRef_elems :
				if elem.get('roleURI') == sub_root_node.label_in_pre_linkbase :
					sub_root_node.set_href(elem.get('xlink:href') )
					break


			self.root_node.append_child(sub_root_node, document_number)


			#各要素を保存するための辞書
			tree_dict = {}


			#presentationLink内の各要素の親子関係を取得し保存する
			for elem in primary_item.select('presentationArc'):

				parent_name = elem.get('xlink:from')
				child_name = elem.get('xlink:to')
				order_str = elem.get('order')
				preferred_label = elem.get('preferredLabel')

				order = None
				if order_str != None :
					order = float(order_str)

				parent = None
				child = None


				if parent_name not in tree_dict:
					parent = YuhoStructureNode(parent_name, 'content')
					tree_dict[parent_name] = parent
				else :
					parent = tree_dict[parent_name]


				if child_name not in tree_dict:
					child = YuhoStructureNode(child_name, 'content')
					tree_dict[child_name] = child
				else :
					child = tree_dict[child_name]


				parent.append_child(child, order)
				child.parent = parent


				if preferred_label != None :
					child.preferred_label = preferred_label



			#親子関係を読み込めたら、各項目のhref属性を設定する
			for key in tree_dict.keys():

				node = tree_dict[key]

				for elem in loc_elems :
					if elem.get('xlink:label') == node.label_in_pre_linkbase :
						node.set_href(elem.get('xlink:href') )
						break




			#保存結果には親が設定されていないノードが存在するため、ここで設定する
			no_parent_node_list = list()
			for key in tree_dict.keys():
				current_node = tree_dict[key]

				if current_node.parent == None :
					no_parent_node_list.append(current_node)


			#idが*Heading*となるノードが最上位ノードなのでこれをまず探す
			#ただし、これは命名規則によるものなので副作用があるかもしれない
			#親無しノードのidとしてHeadingが使われていないという前提の処理
			#もしこれがダメならスキマーファイルを調べて、更に絞り込む必要がある
			heading_node = None
			for no_parent_node in no_parent_node_list :
				if 'Heading' in no_parent_node.id :
					heading_node = no_parent_node
					break


			#EDINET XBRLのガイドラインを見る限り
			#Headingノードは必ず存在するはず
			if heading_node == None :
				raise Exception('no heading node error')


			sub_root_node.append_child(heading_node, 1.0)
			no_parent_node_list.remove(heading_node)


			#Headingノード以外の親無しを処理する
			while len(no_parent_node_list) > 0 :

				#Headingから辿って、子に親無しを持つノードを探す

				#(node, child_index)
				result_tuple = (None, -1)
				source_node = None
				for no_parent_node in no_parent_node_list :

					result_tuple = self.search_node_that_have_target_id_child(heading_node, no_parent_node.id)
					if result_tuple[0] != None :
						source_node = no_parent_node
						break

				#親無しはHeading以下に必ず存在する
				if result_tuple[0] == None :
					raise Exception('no parent node is not exists in heading node')


				node_that_have_target_label_child = result_tuple[0]
				child_index = result_tuple[1]


				#優先ラベルと順序は親無しには絶対設定されていない
				#したがって、挿入先のものを使用する
				source_node.order = node_that_have_target_label_child.children[child_index].order
				source_node.preferred_label = node_that_have_target_label_child.children[child_index].preferred_label

				#親無しを挿入する
				node_that_have_target_label_child.children[child_index] = source_node

				no_parent_node_list.remove(source_node)




	def search_node_that_have_target_id_child(self, node, id) :

		result_node = None
		result_index = -1

		#まず自分自身を調べる
		for index, child in enumerate(node.children) :

			if child.id == id :

				result_node = node
				result_index = index
				break


		#発見したら結果を返す
		if result_node != None :
			return result_node, result_index


		#次に子供を調べる
		for child in node.children :

			result_tuple = self.search_node_that_have_target_id_child(child, id)
			if result_tuple[0] != None :

				return result_tuple[0], result_tuple[1]


		#発見できず
		return None, -1


	#優先ラベル情報を設定する
	def set_preferred_label(self, target_node, parent_preferred_label):

		#親の優先ラベルが設定されており、設定対象の優先ラベルが設定されていない場合のみ
		#設定対象のノードの優先ラベルを設定する

		if target_node.preferred_label == None and parent_preferred_label != None :

			target_node.preferred_label = parent_preferred_label


		for child in target_node.children :
			self.set_preferred_label(child, target_node.preferred_label)



	#指定されたノードに連なるノードを全て表示する
	def print_all_node(self, root_node, depth):

		order = 'None'	
		if root_node.order != None :
			order = root_node.order	

		print('  '*depth,str(root_node.href).split('#')[-1], '  ', order, ' th : label ', root_node.preferred_label)


		root_node.children.sort()
		for child in root_node.children :
			self.print_all_node(child, depth + 1)


	#ノードを検索する
	def search_node(self, id) :

		result = None

		for elm in self :

			if str(elm.href).split('#')[-1] == id :
				result = elm



		return result


	#イテレーターを実装


	#巡回情報スタックへのアクセスは全てこれらの関数郡で行う
	#完全な隠蔽は無理だけど少しはましなはず

	def get_top_walk_info(self):

		if len(self.walk_info_stack) == 0 :
			return None


		else :
			return self.walk_info_stack[-1]

	def pop_walk_info(self) :
		if len(self.walk_info_stack) == 0 :
			return None

		else :
			return self.walk_info_stack.pop()


	def append_walk_info(self, walk_info) :
		self.walk_info_stack.append(walk_info)



	#巡回状況を初期化する
	#デフォルトはルート
	def init_walking_status(self) :
		self.walk_info_stack = list()
		self.walk_info_stack.append(WalkInfo(self.root_node))


	#与えられたノードをルートとして巡回する
	def set_walking_root(self, node) :
		self.walk_info_stack = list()
		self.walk_info_stack.append(WalkInfo(node))



	#イテレータのインターフェース関数
	def __iter__(self):

		return self

	#イテレータのインターフェース関数
	def __next__(self):

		return self.walk_next_node()


	#次の要素に巡回する
	#
	#巡回情報スタックに応じて動作する
	#
	#スタックの最上位の要素を巡回していく
	#子要素がある時はスタックし、親要素に戻るときはポップする
	#スタックが空になった時が巡回を終了するべき時である
	#
	#スタックの一番底が巡回対象となる木構造のルートとなっている
	#部分木のみ巡回したければ、このスタックの一番底を部分木のルートにしておけばよい
	#
	#
	#巡回先の決定アルゴリズム
	#
	#1.巡回情報スタックが空なら巡回を終える
	#  巡回を終える際はスタックに次に巡回する木構造の
	#  最上位ノード情報のみがある状態にしておく
	#
	#2.スタックの最上位が未巡回ならそこを巡回する
	#
	#3.スタックの最上位の子要素を巡回する
	#  子要素を巡回する際はスタックに子要素ノードの情報を積み
	#　再度1から処理を継続する
	#
	#4.子要素を巡回しきったら、親要素を巡回する
	#  親要素を巡回する際はスタックをポップし
	#　再度1から処理を継続する
	#
	def walk_next_node(self):

		#巡回情報が空なら巡回は完了している	
		top_walk_info = self.get_top_walk_info()
		if top_walk_info == None :
			self.end_walking()


		#自身を巡回してないなら自身を巡回する
		if top_walk_info.current_node_returned == False :
			top_walk_info.current_node_returned = True
			return top_walk_info.current_node	


		#いまのノードにとって子ノードの巡回がはじめてなら
		#子ノードの巡回情報の初期化が必要
		if top_walk_info.last_returned_child_index == -1 and len(top_walk_info.current_node.children) != 0 :
			top_walk_info.number_of_children =  len(top_walk_info.current_node.children)

			#初回だけ子ノードのソートを実施する
			top_walk_info.current_node.children.sort()


		#いま巡回する子ノードのインデックスは前回巡回した子ノードのインデックスの次である
		child_index = top_walk_info.last_returned_child_index + 1


		#最後の子ノードを巡回済みであれば親の巡回を再開する
		if top_walk_info.number_of_children <=  child_index :
			self.pop_walk_info()
			return self.walk_next_node()	


		#子ノードを巡回する
		top_walk_info.last_returned_child_index = top_walk_info.last_returned_child_index + 1
		self.append_walk_info(WalkInfo(top_walk_info.current_node.children[child_index]))	
		return self.walk_next_node()


		#ここに到達することはあり得ない


	#巡回を終了する
	def end_walking(self) :
		self.init_walking_status()
		raise StopIteration()


#巡回情報
class WalkInfo():

	def __init__(self, current_node):
		self.current_node = current_node

		#自身を巡回済みか否か
		self.current_node_returned = False

		#子ノードの巡回状況を保持
		self.last_returned_child_index = -1 
		self.number_of_children = 0


#ノード
class YuhoStructureNode():



	def __init__(self, label_in_pre_linkbase, node_kind):


		#ノードの種別
		# 'root'          読み込みのために存在
		# 'document_name' 有報表示構造における大項目
		# 'content'       大項目の下にある構造要素
		self.node_kind = node_kind


		self.label_in_pre_linkbase = label_in_pre_linkbase 
		self.order = None
		self.parent = None
		self.children = list()
		self.preferred_label = None
		self.href = None
		self.id = None



	#href要素を設定する
	def set_href(self, href) :

		self.href = href
		self.id = href.split('#')[-1]



	#子ノードを追加する(順序付き)
	def append_child(self, child, order):
		child.order = order
		self.children.append(child)



	def __lt__(self, other):
		return self.order < other.order



xml_data_getter = XMLDataGetter()

yuho_tree = YuhoStructureTree('.\\S100NROE\\XBRL\PublicDoc\\jpcrp030000-asr-001_E31037-000_2021-12-31_01_2022-03-29_pre.xml', xml_data_getter)
yuho_tree.set_preferred_label(yuho_tree.root_node, None)

yuho_tree.print_all_node(yuho_tree.search_node('rol_ConsolidatedBalanceSheet'), 0)

