import re
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import uuid
import math
import sys

class MermaidToDrawIO:
    def __init__(self):
        self.entities = {}  # 存储实体及其属性
        self.relationships = []  # 存储关系
        self.spacing_x = 320  # 水平间距
        self.spacing_y = 240  # 垂直间距
        self.entity_height = 60  # 实体高度
        self.entity_width = 120  # 实体宽度
        self.attribute_width = 100  # 属性宽度
        self.attribute_height = 50  # 属性高度
        self.relationship_size = 80  # 关系菱形大小
        
    def parse_mermaid(self, mermaid_text):
        """解析Mermaid ER图文本"""
        # 提取实体块
        entity_pattern = r'(\w+)\s*{([^}]*)}'
        entity_matches = re.finditer(entity_pattern, mermaid_text)
        
        for match in entity_matches:
            entity_name = match.group(1)
            attributes_text = match.group(2)
            
            # 解析属性
            attributes = []
            for line in attributes_text.strip().split('\n'):
                line = line.strip()
                if line:
                    attr_parts = line.split()
                    attr_type = attr_parts[0] if attr_parts else "string"
                    attr_name = attr_parts[1] if len(attr_parts) > 1 else "unnamed"
                    is_pk = "PK" in line  # 检查是否是主键
                    is_fk = "FK" in line  # 检查是否是外键
                    attributes.append({
                        "name": attr_name, 
                        "type": attr_type,
                        "is_pk": is_pk,
                        "is_fk": is_fk
                    })
            
            self.entities[entity_name] = {
                "name": entity_name,
                "attributes": attributes
            }
        
        # 提取关系
        relationship_pattern = r'(\w+)\s+(\|\|--\|\||o\|--\|\||\|\|--o\{|\|\|--\|\{|o\{--\|\||\|\{--\|\||--)\s+(\w+)\s*:\s*"?([^"\n]*)"?'
        relationship_matches = re.finditer(relationship_pattern, mermaid_text)
        
        for match in relationship_matches:
            from_entity = match.group(1)
            relationship_type = match.group(2)
            to_entity = match.group(3)
            relationship_name = match.group(4).strip('"')
            
            # 解析关系类型和基数
            from_cardinality = "1"
            to_cardinality = "1"
            
            if "||--||" in relationship_type:
                from_cardinality = "1"
                to_cardinality = "1"
            elif "||--o{" in relationship_type or "||--|{" in relationship_type:
                from_cardinality = "1"
                to_cardinality = "n"
            elif "o{--||" in relationship_type or "|{--||" in relationship_type:
                from_cardinality = "n"
                to_cardinality = "1"
            
            self.relationships.append({
                "from_entity": from_entity,
                "to_entity": to_entity,
                "name": relationship_name,
                "from_cardinality": from_cardinality,
                "to_cardinality": to_cardinality
            })
    
    def create_drawio_xml(self):
        """创建DrawIO XML格式文件"""
        # 创建根元素
        root = ET.Element("mxfile")
        root.set("host", "app.diagrams.net")
        root.set("modified", "2023-07-27T10:00:00.000Z")
        root.set("agent", "5.0 (Macintosh)")
        root.set("version", "20.8.16")
        root.set("type", "device")
        
        diagram = ET.SubElement(root, "diagram")
        diagram.set("id", str(uuid.uuid4()))
        diagram.set("name", "Chen ER图")
        
        mxGraphModel = ET.SubElement(diagram, "mxGraphModel")
        mxGraphModel.set("dx", "0")
        mxGraphModel.set("dy", "0")
        mxGraphModel.set("grid", "1")
        mxGraphModel.set("gridSize", "10")
        mxGraphModel.set("guides", "1")
        mxGraphModel.set("tooltips", "1")
        mxGraphModel.set("connect", "1")
        mxGraphModel.set("arrows", "1")
        mxGraphModel.set("fold", "1")
        mxGraphModel.set("page", "1")
        mxGraphModel.set("pageScale", "1")
        mxGraphModel.set("pageWidth", "1100")
        mxGraphModel.set("pageHeight", "850")
        mxGraphModel.set("background", "#ffffff")
        
        root_cell = ET.SubElement(mxGraphModel, "root")
        
        # 添加基本单元格
        cell_0 = ET.SubElement(root_cell, "mxCell")
        cell_0.set("id", "0")
        
        cell_1 = ET.SubElement(root_cell, "mxCell")
        cell_1.set("id", "1")
        cell_1.set("parent", "0")
        
        # 计算布局
        self._calculate_layout()
        
        # 添加实体和属性
        for entity_name, entity_data in self.entities.items():
            entity_pos = entity_data["position"]
            
            # 创建实体框
            entity_cell = ET.SubElement(root_cell, "mxCell")
            entity_id = str(uuid.uuid4())
            entity_data["id"] = entity_id
            entity_cell.set("id", entity_id)
            entity_cell.set("value", entity_name)
            entity_cell.set("style", "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=16;fontStyle=1;")
            entity_cell.set("vertex", "1")
            entity_cell.set("parent", "1")
            
            geometry = ET.SubElement(entity_cell, "mxGeometry")
            geometry.set("x", str(entity_pos["x"]))
            geometry.set("y", str(entity_pos["y"]))
            geometry.set("width", str(self.entity_width))
            geometry.set("height", str(self.entity_height))
            geometry.set("as", "geometry")
            
            # 创建属性椭圆
            attrs_count = len(entity_data["attributes"])
            for i, attr in enumerate(entity_data["attributes"]):
                attr_cell = ET.SubElement(root_cell, "mxCell")
                attr_id = str(uuid.uuid4())
                attr["id"] = attr_id
                
                attr_style = "ellipse;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;"
                if attr["is_pk"]:
                    attr_style += "fontStyle=4;" # 下划线，表示主键
                
                attr_cell.set("id", attr_id)
                attr_cell.set("value", attr["name"])
                attr_cell.set("style", attr_style)
                attr_cell.set("vertex", "1")
                attr_cell.set("parent", "1")
                
                # 计算属性位置 - 围绕实体的圆形分布
                angle = 2 * math.pi * i / attrs_count
                radius = 180  # 属性围绕实体的半径
                
                # 计算属性位置，使其围绕实体摆放
                attr_x = entity_pos["x"] + self.entity_width/2 + radius * math.cos(angle) - self.attribute_width/2
                attr_y = entity_pos["y"] + self.entity_height/2 + radius * math.sin(angle) - self.attribute_height/2
                
                geometry = ET.SubElement(attr_cell, "mxGeometry")
                geometry.set("x", str(attr_x))
                geometry.set("y", str(attr_y))
                geometry.set("width", str(self.attribute_width))
                geometry.set("height", str(self.attribute_height))
                geometry.set("as", "geometry")
                
                # 连接实体和属性
                edge = ET.SubElement(root_cell, "mxCell")
                edge.set("id", str(uuid.uuid4()))
                edge.set("style", "endArrow=none;html=1;rounded=0;exitX=0.5;exitY=0.5;exitDx=0;exitDy=0;entryX=0.5;entryY=0.5;entryDx=0;entryDy=0;")
                edge.set("edge", "1")
                edge.set("parent", "1")
                edge.set("source", entity_id)
                edge.set("target", attr_id)
                
                geometry = ET.SubElement(edge, "mxGeometry")
                geometry.set("relative", "1")
                geometry.set("as", "geometry")
        
        # 添加关系
        for rel in self.relationships:
            # 确保实体存在
            if rel["from_entity"] not in self.entities or rel["to_entity"] not in self.entities:
                print(f"警告: 关系 {rel['name']} 引用的实体不存在")
                continue
                
            from_entity = self.entities[rel["from_entity"]]
            to_entity = self.entities[rel["to_entity"]]
            
            from_pos = from_entity["position"]
            to_pos = to_entity["position"]
            
            # 创建关系菱形
            relation_cell = ET.SubElement(root_cell, "mxCell")
            relation_id = str(uuid.uuid4())
            rel["id"] = relation_id
            relation_cell.set("id", relation_id)
            relation_cell.set("value", rel["name"])
            relation_cell.set("style", "rhombus;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;")
            relation_cell.set("vertex", "1")
            relation_cell.set("parent", "1")
            
            # 计算关系位置 - 位于两个实体之间
            rel_x = (from_pos["x"] + to_pos["x"]) / 2 
            rel_y = (from_pos["y"] + to_pos["y"]) / 2
            
            # 如果实体水平排列，调整菱形垂直位置
            if abs(from_pos["y"] - to_pos["y"]) < self.entity_height:
                rel_y = from_pos["y"] + self.entity_height + 50
            
            geometry = ET.SubElement(relation_cell, "mxGeometry")
            geometry.set("x", str(rel_x - self.relationship_size/2))
            geometry.set("y", str(rel_y - self.relationship_size/2))
            geometry.set("width", str(self.relationship_size))
            geometry.set("height", str(self.relationship_size))
            geometry.set("as", "geometry")
            
            # 连接from实体和关系
            edge_from = ET.SubElement(root_cell, "mxCell")
            edge_from.set("id", str(uuid.uuid4()))
            edge_from.set("value", rel["from_cardinality"])
            edge_from.set("style", "endArrow=none;html=1;rounded=0;fontSize=14;fontStyle=1;labelBackgroundColor=#FFFFFF;")
            edge_from.set("edge", "1") 
            edge_from.set("parent", "1")
            edge_from.set("source", from_entity["id"])
            edge_from.set("target", relation_id)
            
            geometry_from = ET.SubElement(edge_from, "mxGeometry")
            geometry_from.set("relative", "1")
            geometry_from.set("as", "geometry")
            
            # 连接关系和to实体
            edge_to = ET.SubElement(root_cell, "mxCell")
            edge_to.set("id", str(uuid.uuid4()))
            edge_to.set("value", rel["to_cardinality"])
            edge_to.set("style", "endArrow=none;html=1;rounded=0;fontSize=14;fontStyle=1;labelBackgroundColor=#FFFFFF;")
            edge_to.set("edge", "1")
            edge_to.set("parent", "1")
            edge_to.set("source", relation_id)
            edge_to.set("target", to_entity["id"])
            
            geometry_to = ET.SubElement(edge_to, "mxGeometry")
            geometry_to.set("relative", "1")
            geometry_to.set("as", "geometry")
        
        # 生成XML字符串并格式化
        xml_str = ET.tostring(root, encoding='utf-8')
        parsed_xml = minidom.parseString(xml_str)
        pretty_xml = parsed_xml.toprettyxml(indent="  ")
        
        return pretty_xml
    
    def _calculate_layout(self):
        """计算实体和关系的布局位置"""
        grid_size = math.ceil(math.sqrt(len(self.entities)))
        
        # 为每个实体分配网格位置
        i = 0
        for entity_name in self.entities:
            row = i // grid_size
            col = i % grid_size
            
            self.entities[entity_name]["position"] = {
                "x": 100 + col * self.spacing_x,
                "y": 100 + row * self.spacing_y
            }
            i += 1
    
    def convert(self, mermaid_text, output_file=None):
        """转换Mermaid文本到DrawIO XML并保存文件"""
        self.parse_mermaid(mermaid_text)
        xml = self.create_drawio_xml()
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(xml)
            return f"已保存到 {output_file}"
        
        return xml


def extract_mermaid_from_markdown(md_file):
    """从Markdown文件中提取Mermaid代码块"""
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    mermaid_pattern = r'```mermaid\s+(.*?)\s+```'
    match = re.search(mermaid_pattern, content, re.DOTALL)
    
    if match:
        return match.group(1)
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python mermaid_to_chen_er.py <markdown文件> [输出文件.drawio]")
        sys.exit(1)
    
    md_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "er_diagram.drawio"
    
    mermaid_text = extract_mermaid_from_markdown(md_file)
    if not mermaid_text:
        print(f"在 {md_file} 中没有找到Mermaid代码块")
        sys.exit(1)
    
    converter = MermaidToDrawIO()
    result = converter.convert(mermaid_text, output_file)
    print(result) 